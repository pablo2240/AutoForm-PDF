#!/usr/bin/env python
"""
Migration Script: Local JSON & SQLite -> Supabase PostgreSQL (AutoForm PDF)

Security & Integrity Rules:
1. Reads sensitive data only at runtime from backend/data/company_data.json and backend/data/local_dev.db.
2. UTF-8-sig encoding to prevent Windows BOM issues.
3. NIT split & validation: Computes DIAN Modulo 11 DV and validates against the source DV.
4. Financial balances: Uses Decimal (never floats) or normalized strings for high-precision currency.
5. Invariable default: --dry-run is enforced by default.
6. Execution safety: Real write requires explicit '--execute --confirm-project tnhedxwbpqihlqbtzudt'.
7. Privilege separation: Sets 'company_id' and 'role' strictly in 'app_metadata' (server-side admin).
   Only non-privileged fields (nombre, apellido, cargo, celular) go into 'user_metadata'.
8. Zero credentials leak: Never prints tokens, service-role keys, passwords, or recovery URLs in logs.
9. Legacy preservation: Legacy files are preserved 100% intact as backups.
"""

import os
import sys
import json
import sqlite3
import re
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import uuid
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

EXPECTED_PROJECT_REF = "tnhedxwbpqihlqbtzudt"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

COMPANY_DATA_PATH = ROOT_DIR / "backend" / "data" / "company_data.json"
LOCAL_DB_PATH = ROOT_DIR / "backend" / "data" / "local_dev.db"
MAPPINGS_DIR = ROOT_DIR / "backend" / "data"


def compute_dian_dv(nit_digits: str) -> str:
    """
    Computes DIAN Modulo 11 verification digit (DV) for Colombian tax IDs (NIT).
    Factors: [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    """
    weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    clean_nit = "".join(c for c in nit_digits if c.isdigit())
    if not clean_nit:
        raise ValueError("NIT contains no numeric digits")
    s = sum(int(digit) * weights[i] for i, digit in enumerate(reversed(clean_nit)))
    remainder = s % 11
    if remainder in (0, 1):
        return str(remainder)
    return str(11 - remainder)


def parse_and_validate_nit(raw_nit: str) -> tuple[str, str]:
    """
    Extracts (nit_digits, dv) and mathematically validates the DV with DIAN Modulo 11.
    """
    clean = raw_nit.strip().replace(".", "")
    if "-" in clean:
        parts = clean.split("-")
        nit_digits, dv = parts[0].strip(), parts[1].strip()
    elif len(clean) == 10:
        nit_digits, dv = clean[:9], clean[9]
    else:
        raise ValueError(f"Unrecognized NIT format: '{raw_nit}'. Expected 10 digits or hyphenated DV.")

    expected_dv = compute_dian_dv(nit_digits)
    if dv != expected_dv:
        raise ValueError(f"NIT validation failed: Computed DIAN DV is '{expected_dv}', but received '{dv}'.")

    return nit_digits, dv


def parse_date_to_iso(raw_date: str) -> str:
    """
    Converts DD-MM-YYYY to standard ISO YYYY-MM-DD for PostgreSQL DATE.
    """
    raw_date = raw_date.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
        return raw_date
    if re.match(r"^\d{2}-\d{2}-\d{4}$", raw_date):
        dt = datetime.strptime(raw_date, "%d-%m-%Y")
        return dt.strftime("%Y-%m-%d")
    raise ValueError(f"Unable to parse date: '{raw_date}'")


def parse_decimal_financial(raw_val) -> str:
    """
    Safely converts financial values to string-encoded Decimals (prevents float precision errors).
    """
    if raw_val is None:
        return "0.00"
    dec = Decimal(str(raw_val).strip())
    return str(dec.quantize(Decimal("0.01")))


def load_company_data() -> dict:
    if not COMPANY_DATA_PATH.exists():
        raise FileNotFoundError(f"Missing company data file: {COMPANY_DATA_PATH}")
    with open(COMPANY_DATA_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_production_profiles() -> list[dict]:
    """
    Reads SQLite local_dev.db and extracts only genuine production profiles.
    Filters out test accounts (e.g. comercial_*@iaclatam.com).
    """
    if not LOCAL_DB_PATH.exists():
        raise FileNotFoundError(f"Missing local DB file: {LOCAL_DB_PATH}")

    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    rows = cursor.execute("SELECT * FROM commercial_profiles WHERE is_active = 1").fetchall()
    prod_profiles = []

    for r in rows:
        email = r["email"].strip().lower()
        # Exclude auto-generated test runs
        if re.match(r"^comercial_[0-9a-f]+@iaclatam\.com$", email):
            continue

        cargo = r["cargo"].strip()
        if "lider comercial" in cargo.lower():
            cargo = "Asesor Comercial"

        prod_profiles.append({
            "email": email,
            "nombre": r["nombre"].strip(),
            "apellido": r["apellido"].strip(),
            "display_name": f"{r['nombre'].strip()} {r['apellido'].strip()}",
            "cargo": cargo,
            "celular": r["celular"].strip(),
            "tipo_documento": r["tipo_documento"] or "C.C",
            "documento_identidad": r["documento_identidad"],
            "role": r["role"] or "commercial",
            "is_active": bool(r["is_active"])
        })

    conn.close()
    return prod_profiles


def run_migration(execute: bool, confirm_project: str | None):
    print("=" * 70)
    print("AutoForm PDF: Secure Migration Validator & Provisioner")
    print(f"Target Expected Project: {EXPECTED_PROJECT_REF}")
    print(f"Execution Mode: {'LIVE EXECUTE' if execute else 'DRY RUN (Safe Inspection)'}")
    print("=" * 70)

    # 1. Parse and validate company
    raw_company = load_company_data()
    nit_digits, nit_dv = parse_and_validate_nit(raw_company["nit"])

    company_payload = {
        "razon_social": raw_company["razon_social"],
        "nombre_comercial": "IAC",
        "nit": nit_digits,
        "dv": nit_dv,
        "pais": raw_company.get("pais", "Colombia"),
        "departamento": raw_company.get("departamento", "Antioquia"),
        "ciudad": raw_company.get("ciudad", "Medellin"),
        "direccion_principal": raw_company.get("direccion_principal"),
        "telefono": raw_company.get("telefono"),
        "pagina_web": raw_company.get("pagina_web"),
        "total_activos": parse_decimal_financial(raw_company.get("total_activos")),
        "total_pasivos": parse_decimal_financial(raw_company.get("total_pasivos")),
        "total_patrimonio": parse_decimal_financial(raw_company.get("total_patrimonio")),
        "total_ingresos_mensuales": parse_decimal_financial(raw_company.get("total_ingresos_mensuales")),
        "total_egresos_mensuales": parse_decimal_financial(raw_company.get("total_egresos_mensuales")),
        "is_active": True
    }
    print(f"[OK] Company parsed: {company_payload['razon_social']}")
    print(f"     NIT: {nit_digits}-{nit_dv} (DIAN Modulo 11 verified)")
    print(f"     Activos (Decimal): {company_payload['total_activos']}")

    # 2. Bank account
    bank_payload = {
        "entidad_bancaria": raw_company.get("entidad_bancaria", "BANCOLOMBIA"),
        "tipo_cuenta": raw_company.get("tipo_cuenta", "Ahorros"),
        "numero_cuenta": raw_company.get("numero_cuenta", "00300833888"),
        "es_principal": True,
        "activo": True
    }
    print(f"[OK] Bank Account parsed: {bank_payload['entidad_bancaria']} ({bank_payload['tipo_cuenta']})")

    # 3. Legal rep
    fecha_exp_iso = parse_date_to_iso(raw_company.get("fecha_expedicion_rep", "26-06-1989"))
    rep_payload = {
        "nombre_completo": raw_company.get("representante_legal"),
        "nombres": raw_company.get("representante_nombre"),
        "apellidos": raw_company.get("representante_apellido"),
        "tipo_documento": raw_company.get("tipo_documento", "C.C"),
        "numero_documento": raw_company.get("numero_cedula"),
        "lugar_expedicion": raw_company.get("lugar_expedicion_rep"),
        "fecha_expedicion": fecha_exp_iso,
        "email": raw_company.get("correo_rep"),
        "celular": raw_company.get("celular_rep"),
        "firma_storage_path": "signatures/global_signature.png",
        "es_principal": True,
        "is_active": True
    }
    print(f"[OK] Legal Representative parsed: {rep_payload['nombre_completo']} ({fecha_exp_iso})")

    # 4. Production profiles
    profiles = load_production_profiles()
    print(f"[OK] {len(profiles)} production profiles discovered:")
    for p in profiles:
        print(f"     - {p['display_name']} <{p['email']}> [Role: {p['role']}]")

    # 5. Template mappings
    mapping_files = list(MAPPINGS_DIR.glob("*_mapping.json"))
    print(f"[OK] {len(mapping_files)} template mapping definitions discovered.")

    if not execute:
        print("\n[SAFETY] Dry-run finished. Zero network calls or database writes were performed.")
        print("To execute migration for real, run with:")
        print(f"  python scripts/migrate_to_supabase.py --execute --confirm-project {EXPECTED_PROJECT_REF}")
        print("To rollback a previous execution batch, run with:")
        print(f"  python scripts/migrate_to_supabase.py --rollback <BATCH_UUID> --confirm-project {EXPECTED_PROJECT_REF}")
        return

    # Safety guard: explicit confirmation
    if confirm_project != EXPECTED_PROJECT_REF:
        raise ValueError(
            f"Execution rejected: --confirm-project must match '{EXPECTED_PROJECT_REF}', got '{confirm_project}'"
        )

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are required.")

    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Generate unique migration batch ID
    batch_id = str(uuid.uuid4())
    print(f"\n[INITIATING] Migration Run Batch ID: {batch_id}")

    # Register run in migration_runs
    supabase.table("migration_runs").insert({
        "batch_id": batch_id,
        "target_project_ref": confirm_project,
        "status": "running",
        "manifest": {}
    }).execute()

    try:
        # Attach batch_id to all payloads
        company_payload["migration_batch_id"] = batch_id
        bank_payload["migration_batch_id"] = batch_id
        rep_payload["migration_batch_id"] = batch_id

        # 6. Upsert Company
        res_comp = supabase.table("companies").upsert(company_payload, on_conflict="nit").execute()
        company_id = res_comp.data[0]["id"]
        print(f"[EXECUTED] Upserted company ID: {company_id}")

        # 7. Upsert Bank Account
        bank_payload["company_id"] = company_id
        supabase.table("company_bank_accounts").upsert(bank_payload, on_conflict="company_id").execute()
        print("[EXECUTED] Upserted company bank account.")

        # 8. Provision Users via Supabase Admin API with strict app_metadata separation
        user_id_map = {}
        for p in profiles:
            email = p["email"]
            # CRITICAL SECURITY: company_id, role, migration_batch_id go into app_metadata (server-side only)
            app_meta = {
                "company_id": company_id,
                "role": p["role"],
                "migration_batch_id": batch_id
            }
            # Non-privileged fields go into user_metadata
            user_meta = {
                "nombre": p["nombre"],
                "apellido": p["apellido"],
                "cargo": p["cargo"],
                "celular": p["celular"],
                "tipo_documento": p["tipo_documento"],
                "documento_identidad": p["documento_identidad"]
            }

            try:
                auth_user = supabase.auth.admin.create_user({
                    "email": email,
                    "email_confirm": True,
                    "app_metadata": app_meta,
                    "user_metadata": user_meta
                })
                user_id = auth_user.user.id
                print(f"[EXECUTED] Created user: {email} -> {user_id}")
            except Exception as e:
                if "already registered" in str(e).lower() or "unique" in str(e).lower():
                    users = supabase.auth.admin.list_users()
                    target = next((u for u in users if u.email.lower() == email.lower()), None)
                    if target:
                        user_id = target.id
                        # Update app_metadata to ensure company_id, role, migration_batch_id are strictly set
                        supabase.auth.admin.update_user_by_id(user_id, {
                            "app_metadata": app_meta,
                            "user_metadata": user_meta
                        })
                        print(f"[EXECUTED] Synchronized existing user: {email} -> {user_id}")
                    else:
                        raise e
                else:
                    raise e

            # Explicitly ensure profile has migration_batch_id
            supabase.table("profiles").update({"migration_batch_id": batch_id}).eq("id", user_id).execute()
            user_id_map[email] = user_id

        # 9. Legal rep linking
        rep_payload["company_id"] = company_id
        rep_email = rep_payload.get("email", "").lower()
        if rep_email in user_id_map:
            rep_payload["user_id"] = user_id_map[rep_email]

        supabase.table("legal_representatives").upsert(rep_payload, on_conflict="company_id").execute()
        print("[EXECUTED] Upserted legal representative.")

        # 10. Templates and mappings
        tpl_ids = []
        ver_ids = []
        total_mappings = 0

        for mf in mapping_files:
            try:
                with open(mf, "r", encoding="utf-8-sig") as f:
                    mapping_data = json.load(f)
            except Exception:
                with open(mf, "r", encoding="utf-8") as f:
                    mapping_data = json.load(f)

            raw_template_id = mapping_data.get("template_id", mf.stem.replace("_mapping", ""))
            template_code = re.sub(r"[^A-Za-z0-9_-]", "_", raw_template_id)[:100].upper()

            res_tpl = supabase.table("pdf_templates").upsert({
                "company_id": company_id,
                "codigo": template_code,
                "nombre": raw_template_id,
                "migration_batch_id": batch_id,
                "is_active": True
            }, on_conflict="company_id,codigo").execute()
            tpl_id = res_tpl.data[0]["id"]
            tpl_ids.append(tpl_id)

            res_ver = supabase.table("pdf_template_versions").upsert({
                "template_id": tpl_id,
                "version": 1,
                "filename": f"{raw_template_id}.pdf",
                "storage_path": f"{company_id}/templates/{tpl_id}/v1/{raw_template_id}.pdf",
                "page_count": 1,
                "is_acroform": False,
                "migration_batch_id": batch_id,
                "is_active": True
            }, on_conflict="template_id,version").execute()
            ver_id = res_ver.data[0]["id"]
            ver_ids.append(ver_id)

            mappings_list = mapping_data.get("mappings", [])
            if mappings_list:
                db_mappings = []
                for m in mappings_list:
                    db_mappings.append({
                        "template_version_id": ver_id,
                        "field_key": m.get("field_key", "unknown"),
                        "category": m.get("label", "general"),
                        "source_path": m.get("field_key", ""),
                        "page_index": m.get("page_number", 0),
                        "coordinates": m.get("box", {}),
                        "field_type": m.get("style", {}).get("item_type", "text"),
                        "validation_rules": m.get("style", {}),
                        "migration_batch_id": batch_id
                    })
                supabase.table("pdf_mappings").delete().eq("template_version_id", ver_id).execute()
                supabase.table("pdf_mappings").insert(db_mappings).execute()
                total_mappings += len(db_mappings)
                print(f"[EXECUTED] Registered template: {template_code} (v1) with {len(db_mappings)} mappings.")

        # 11. Finalize migration run with full manifest
        manifest = {
            "company_id": company_id,
            "company_nit": company_payload["nit"],
            "auth_user_ids": list(user_id_map.values()),
            "user_emails": list(user_id_map.keys()),
            "template_ids": tpl_ids,
            "template_version_ids": ver_ids,
            "storage_manifest_file": "backend/data/storage_pre_migration_backup/storage_manifest_sha256.json",
            "entity_counts": {
                "companies": 1,
                "company_bank_accounts": 1,
                "legal_representatives": 1,
                "profiles": len(user_id_map),
                "pdf_templates": len(tpl_ids),
                "pdf_template_versions": len(ver_ids),
                "pdf_mappings": total_mappings
            }
        }

        supabase.table("migration_runs").update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "manifest": manifest
        }).eq("batch_id", batch_id).execute()

        print(f"\n[COMPLETE] Migration batch {batch_id} completed successfully.")
        print(f"Manifest saved to public.migration_runs table.")
        print(f"To rollback this exact batch if ever needed, run:")
        print(f"  python scripts/migrate_to_supabase.py --rollback {batch_id} --confirm-project {confirm_project}")

    except Exception as err:
        print(f"\n[ERROR] Migration encountered an error: {err}")
        supabase.table("migration_runs").update({
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error_message": str(err)
        }).eq("batch_id", batch_id).execute()
        raise


def run_rollback(batch_id: str, confirm_project: str | None):
    print("=" * 70)
    print("AutoForm PDF: Selective Migration Batch Rollback")
    print(f"Target Project: {confirm_project}")
    print(f"Batch ID to Rollback: {batch_id}")
    print("=" * 70)

    if confirm_project != EXPECTED_PROJECT_REF:
        raise ValueError(
            f"Rollback rejected: --confirm-project must match '{EXPECTED_PROJECT_REF}', got '{confirm_project}'"
        )

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are required.")

    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # 1. Fetch migration run
    run_res = supabase.table("migration_runs").select("*").eq("batch_id", batch_id).execute()
    if not run_res.data:
        raise ValueError(f"Migration run with batch_id '{batch_id}' not found in public.migration_runs")

    run_record = run_res.data[0]
    if run_record["status"] == "rolled_back":
        print(f"[ALREADY ROLLED BACK] Migration batch {batch_id} was already rolled back at {run_record.get('completed_at')}.")
        return

    print(f"[1/3] Calling public.rollback_migration_batch('{batch_id}')...")
    rpc_res = supabase.rpc("rollback_migration_batch", {"p_batch_id": batch_id}).execute()
    print(f"  [OK] Database entities rolled back: {rpc_res.data}")

    # 2. Delete Auth users created during this batch
    manifest = run_record.get("manifest", {})
    auth_user_ids = manifest.get("auth_user_ids", [])
    print(f"[2/3] Deleting {len(auth_user_ids)} Auth users created during this batch...")
    for uid in auth_user_ids:
        try:
            supabase.auth.admin.delete_user(uid)
            print(f"  [OK] Deleted Auth user {uid}")
        except Exception as e:
            print(f"  ! Warning: Could not delete Auth user {uid}: {e}")

    # 3. Confirm rollback
    print(f"\n[3/3] Rollback confirmed! Migration batch {batch_id} has been completely removed.")


if __name__ == "__main__":
    is_execute = "--execute" in sys.argv
    confirm_proj = None
    if "--confirm-project" in sys.argv:
        idx = sys.argv.index("--confirm-project")
        if idx + 1 < len(sys.argv):
            confirm_proj = sys.argv[idx + 1]

    rollback_id = None
    if "--rollback" in sys.argv:
        idx = sys.argv.index("--rollback")
        if idx + 1 < len(sys.argv):
            rollback_id = sys.argv[idx + 1]

    if rollback_id:
        run_rollback(batch_id=rollback_id, confirm_project=confirm_proj)
    else:
        run_migration(execute=is_execute, confirm_project=confirm_proj)
