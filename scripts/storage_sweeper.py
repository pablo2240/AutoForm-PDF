#!/usr/bin/env python
"""
Storage Sweeper: Out-of-band Orphan Artifact Cleanup (ADR-0011 P5)

Scans Supabase Storage buckets ('templates', 'generated-pdfs') for orphaned files
left behind by crashed requests, network disconnects, or aborted transactions.

Safety Invariants:
1. --dry-run is strictly enforced by default. Real deletions require --prune.
2. Production protection: When operating against production (tnhedxwbpqihlqbtzudt),
   --prune requires explicit '--confirm-project tnhedxwbpqihlqbtzudt'.
3. Grace period (--grace-minutes 60): Recent uploads are never pruned to avoid race conditions
   with in-flight uploads.
4. Authoritative DB reconciliation: Checks user_documents and form_fill_history.
"""

import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Set, Any, Optional
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

EXPECTED_PROD_PROJECT = "tnhedxwbpqihlqbtzudt"

try:
    from backend.auth_supabase import get_supabase_admin_client
except ImportError:
    # Allow running directly from repo root
    sys.path.insert(0, str(ROOT_DIR))
    from backend.auth_supabase import get_supabase_admin_client


def normalize_storage_path(bucket: str, raw_path: str) -> str:
    """Normalizes path by stripping leading slashes and optional bucket prefixes."""
    path = raw_path.strip().lstrip("/")
    if path.startswith(f"{bucket}/"):
        path = path[len(bucket) + 1:]
    return path


def list_recursive_storage_objects(admin_client, bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
    """
    Recursively enumerates all objects in a Supabase Storage bucket.
    Traverses folder hierarchies (company_id/user_id/filename.pdf).
    """
    found_objects: List[Dict[str, Any]] = []
    try:
        items = admin_client.storage.from_(bucket_name).list(path=prefix, options={"limit": 1000})
        for item in items:
            name = item.get("name")
            if not name or name == ".emptyFolderPlaceholder":
                continue

            current_path = f"{prefix}/{name}" if prefix else name
            # In Supabase Storage, folders have id == None or metadata is None / lacking mimetype
            metadata = item.get("metadata") or {}
            is_folder = item.get("id") is None and not metadata.get("mimetype")

            if is_folder:
                # Recurse into directory
                sub_items = list_recursive_storage_objects(admin_client, bucket_name, prefix=current_path)
                found_objects.extend(sub_items)
            else:
                found_objects.append({
                    "bucket": bucket_name,
                    "key": current_path,
                    "name": name,
                    "id": item.get("id"),
                    "metadata": metadata,
                    "created_at": item.get("created_at") or metadata.get("created_at"),
                    "updated_at": item.get("updated_at") or metadata.get("updated_at"),
                })
    except Exception as e:
        print(f"[WARN] Error listing storage objects in {bucket_name}/{prefix}: {e}")

    return found_objects


def fetch_registered_keys_for_bucket(admin_client, bucket_name: str) -> Set[str]:
    """
    Queries relational tables to build the authoritative set of registered storage paths.
    - 'templates': user_documents.storage_path
    - 'generated-pdfs': form_fill_history.output_storage_path
    """
    registered_keys: Set[str] = set()

    if bucket_name == "templates":
        try:
            # Query all user_documents (both active and inactive)
            res = admin_client.table("user_documents").select("storage_path").execute()
            if res.data:
                for row in res.data:
                    raw_sp = row.get("storage_path")
                    if raw_sp:
                        norm = normalize_storage_path("templates", raw_sp)
                        registered_keys.add(norm)
                        registered_keys.add(f"templates/{norm}")
        except Exception as e:
            print(f"[ERROR] Failed to query user_documents for registered templates: {e}")
            raise

    elif bucket_name == "generated-pdfs":
        try:
            res = admin_client.table("form_fill_history").select("output_storage_path").execute()
            if res.data:
                for row in res.data:
                    raw_sp = row.get("output_storage_path")
                    if raw_sp:
                        norm = normalize_storage_path("generated-pdfs", raw_sp)
                        registered_keys.add(norm)
                        registered_keys.add(f"generated-pdfs/{norm}")
        except Exception as e:
            print(f"[ERROR] Failed to query form_fill_history for registered generated-pdfs: {e}")
            raise

    return registered_keys


def parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parses ISO timestamp string into timezone-aware datetime."""
    if not ts_str:
        return None
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


def run_sweeper(
    buckets: List[str],
    grace_minutes: int,
    prune_mode: bool,
    confirm_project: Optional[str]
) -> Dict[str, Any]:
    """
    Executes the orphan sweeper across designated buckets.
    Returns audit metrics.
    """
    admin_client = get_supabase_admin_client()
    now_utc = datetime.now(timezone.utc)
    grace_delta = timedelta(minutes=grace_minutes)

    # Check project safety
    supabase_url = os.getenv("SUPABASE_URL", "")
    is_prod_ref = EXPECTED_PROD_PROJECT in supabase_url

    if prune_mode and is_prod_ref:
        if confirm_project != EXPECTED_PROD_PROJECT:
            print(f"[CRITICAL SAFETY ERROR] Pruning production storage ({EXPECTED_PROD_PROJECT}) requires: ")
            print(f"    --confirm-project {EXPECTED_PROD_PROJECT}")
            sys.exit(1)

    print("=" * 70)
    print("AutoForm PDF - Storage Sweeper (ADR-0011 P5)")
    print(f"Target Environment: {'PRODUCTION (' + EXPECTED_PROD_PROJECT + ')' if is_prod_ref else 'NON-PROD'}")
    print(f"Execution Mode:     {'*** PRUNE (PERMANENT DELETE) ***' if prune_mode else '[DRY-RUN - SAFE AUDIT ONLY]'}")
    print(f"Grace Period:       {grace_minutes} minutes")
    print(f"Target Buckets:     {', '.join(buckets)}")
    print(f"Timestamp (UTC):    {now_utc.isoformat()}")
    print("=" * 70)

    total_scanned = 0
    total_valid = 0
    total_protected = 0
    total_orphans = 0
    total_pruned = 0
    reclaimed_bytes = 0

    orphan_details = []

    for bucket in buckets:
        print(f"\n[INFO] Scanning bucket: '{bucket}'...")
        registered_keys = fetch_registered_keys_for_bucket(admin_client, bucket)
        print(f"       Found {len(registered_keys)} registered storage references in database.")

        storage_objects = list_recursive_storage_objects(admin_client, bucket)
        print(f"       Found {len(storage_objects)} total storage objects in '{bucket}'.")

        for obj in storage_objects:
            total_scanned += 1
            key = obj["key"]
            norm_key = normalize_storage_path(bucket, key)
            raw_size = obj.get("metadata", {}).get("size") or 0

            # 1. Check if registered in DB
            is_registered = norm_key in registered_keys or f"{bucket}/{norm_key}" in registered_keys
            if is_registered:
                total_valid += 1
                continue

            # 2. Check grace period
            created_ts = parse_timestamp(obj.get("created_at") or obj.get("updated_at"))
            if created_ts:
                age = now_utc - created_ts
                if age < grace_delta:
                    total_protected += 1
                    print(f"       [PROTECTED] {bucket}/{key} (Age: {age.total_seconds() / 60:.1f}m < {grace_minutes}m)")
                    continue

            # 3. Orphan confirmed!
            total_orphans += 1
            reclaimed_bytes += raw_size
            orphan_details.append({
                "bucket": bucket,
                "key": key,
                "size_kb": round(raw_size / 1024, 2) if raw_size else 0.0,
                "created_at": obj.get("created_at")
            })

            if prune_mode:
                try:
                    admin_client.storage.from_(bucket).remove([key])
                    total_pruned += 1
                    print(f"       [PRUNED] Deleted orphan: {bucket}/{key} ({raw_size / 1024:.1f} KB)")
                except Exception as del_err:
                    print(f"       [ERROR] Failed to prune {bucket}/{key}: {del_err}")
            else:
                print(f"       [ORPHAN DETECTED] {bucket}/{key} ({raw_size / 1024:.1f} KB, Created: {obj.get('created_at')})")

    print("\n" + "=" * 70)
    print("Storage Sweeper Summary Report")
    print(f"Total Objects Scanned:       {total_scanned}")
    print(f"Valid / Registered in DB:    {total_valid}")
    print(f"Protected by Grace Period:   {total_protected}")
    print(f"Orphaned Objects Detected:   {total_orphans}")
    print(f"Orphaned Objects Pruned:     {total_pruned if prune_mode else 0}")
    print(f"Estimated Space Reclaimed:   {reclaimed_bytes / 1024:.2f} KB ({reclaimed_bytes / (1024 * 1024):.3f} MB)")
    if not prune_mode:
        print("[NOTICE] No objects were deleted. Run with --prune to purge detected orphans.")
    print("=" * 70)

    return {
        "total_scanned": total_scanned,
        "total_valid": total_valid,
        "total_protected": total_protected,
        "total_orphans": total_orphans,
        "total_pruned": total_pruned,
        "reclaimed_bytes": reclaimed_bytes,
        "orphan_details": orphan_details
    }


def main():
    parser = argparse.ArgumentParser(description="AutoForm PDF Storage Sweeper (ADR-0011 P5)")
    parser.add_argument(
        "--bucket",
        type=str,
        default="templates",
        choices=["templates", "generated-pdfs"],
        help="Target storage bucket to sweep (default: templates)"
    )
    parser.add_argument(
        "--all-buckets",
        action="store_true",
        help="Scan both 'templates' and 'generated-pdfs' buckets"
    )
    parser.add_argument(
        "--grace-minutes",
        type=int,
        default=60,
        help="In-flight safety threshold in minutes (default: 60)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Perform read-only audit without deleting files (default)"
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Permanently delete identified orphaned storage objects"
    )
    parser.add_argument(
        "--confirm-project",
        type=str,
        default=None,
        help=f"Required confirmation string when pruning production ({EXPECTED_PROD_PROJECT})"
    )

    args = parser.parse_args()

    prune_mode = bool(args.prune)
    buckets = ["templates", "generated-pdfs"] if args.all_buckets else [args.bucket]

    run_sweeper(
        buckets=buckets,
        grace_minutes=args.grace_minutes,
        prune_mode=prune_mode,
        confirm_project=args.confirm_project
    )


if __name__ == "__main__":
    main()
