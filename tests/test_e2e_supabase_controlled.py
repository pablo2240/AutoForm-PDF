import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Select staging credentials by default for destructive E2E tests
SUPABASE_URL = os.environ.get("SUPABASE_STAGING_URL") or os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_STAGING_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_STAGING_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Sync backend auth module to use the same target environment
import backend.auth_supabase as auth_mod
auth_mod.SUPABASE_URL = SUPABASE_URL
auth_mod.SUPABASE_ANON_KEY = SUPABASE_ANON_KEY
auth_mod.SUPABASE_SERVICE_ROLE_KEY = SUPABASE_SERVICE_ROLE_KEY
auth_mod.EXPECTED_ISSUER = f"{SUPABASE_URL.rstrip('/')}/auth/v1"
auth_mod.JWKS_URL = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
auth_mod.jwks_client = auth_mod.jwt.PyJWKClient(auth_mod.JWKS_URL, cache_jwk_set=True, lifespan=3600)

from fastapi.testclient import TestClient
from supabase import create_client
from backend.main import app

TEST_COMPANY_ID = "00000000-0000-0000-0000-000000000001"
TEST_ADMIN_EMAIL = "temp_admin_test@iaclatam.com"
TEST_ADMIN_PASS = "TestAdminSecurePassword2026!#"
TEST_COMM_EMAIL = "temp_comm_test@iaclatam.com"
TEST_COMM_PASS = "TestCommSecurePassword2026!#"

OTHER_COMPANY_ID = "00000000-0000-0000-0000-000000000002"
OTHER_USER_EMAIL = "temp_other_test@iaclatam.com"
OTHER_USER_PASS = "TestOtherSecurePassword2026!#"

TEST_TPL_ID = "00000000-0000-0000-0000-000000000010"
TEST_VER_ID = "00000000-0000-0000-0000-000000000020"

client = TestClient(app)

def run_controlled_e2e_test():
    print("\n=======================================================")
    print("STARTING CONTROLLED E2E TEST: Supabase Integration")
    print(f"Target Environment URL: {SUPABASE_URL}")
    print("=======================================================")

    # Production safety guard: Unconditional block against the production project
    prod_ref = os.getenv("SUPABASE_PRODUCTION_REF", "tnhedxwbpqihlqbtzudt")
    if prod_ref in SUPABASE_URL:
        raise RuntimeError(
            f"CRITICAL SECURITY GUARD: Execution against production Supabase project '{prod_ref}' is UNCONDITIONALLY BLOCKED.\n"
            "Destructive E2E tests must run exclusively against the separate staging environment.\n"
            "There is no bypass or override for this safety block."
        )
    
    admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    anon_supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    created_storage_paths = []
    created_user_ids = []
    
    try:
        # Pre-cleanup in case of dirty state
        print("[0/7] Pre-test reset of test companies and auth users...")
        try:
            admin_supabase.table("form_fill_history").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("pdf_mappings").delete().eq("template_version_id", TEST_VER_ID).execute()
            admin_supabase.table("pdf_template_versions").delete().eq("id", TEST_VER_ID).execute()
            admin_supabase.table("pdf_templates").delete().eq("id", TEST_TPL_ID).execute()
            admin_supabase.table("legal_representatives").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("company_bank_accounts").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("profiles").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("companies").delete().in_("id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()

            # Clean lingering test auth users
            all_users = admin_supabase.auth.admin.list_users()
            for u in all_users:
                if u.email in [TEST_ADMIN_EMAIL, TEST_COMM_EMAIL, OTHER_USER_EMAIL]:
                    admin_supabase.auth.admin.delete_user(u.id)
        except Exception:
            pass
        
        # 1. Provision Test Company and Legal Representative
        print("[1/7] Provisioning test company and legal representative...")
        admin_supabase.table("companies").insert({
            "id": TEST_COMPANY_ID,
            "nit": "900000001",
            "dv": "1",
            "pais": "Colombia",
            "razon_social": "IAC Latam Test S.A.S."
        }).execute()

        admin_supabase.table("legal_representatives").insert({
            "company_id": TEST_COMPANY_ID,
            "nombre_completo": "Guillermo Humberto Canon Sarria",
            "nombres": "Guillermo Humberto",
            "apellidos": "Canon Sarria",
            "tipo_documento": "CC",
            "numero_documento": "98555384",
            "es_principal": True,
            "is_active": True
        }).execute()
        print("  [OK] Test company provisioned.")

        # 2. Provision Admin User via Supabase Admin API
        print("[2/7] Creating test admin user via Supabase Auth Admin...")
        admin_create_res = admin_supabase.auth.admin.create_user({
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASS,
            "email_confirm": True,
            "app_metadata": {
                "company_id": TEST_COMPANY_ID,
                "role": "admin"
            },
            "user_metadata": {
                "nombre": "Admin",
                "apellido": "Tester",
                "cargo": "Administrador General",
                "celular": "3001234567"
            }
        })
        admin_uid = admin_create_res.user.id
        created_user_ids.append(admin_uid)
        print(f"  [OK] Admin created (UID: {admin_uid}).")

        # Verify handle_new_user trigger created profile in public.profiles
        prof_res = admin_supabase.table("profiles").select("*").eq("id", admin_uid).single().execute()
        assert prof_res.data is not None, "Profile was not created by handle_new_user() trigger!"
        assert prof_res.data["role"] == "admin", f"Expected admin role, got {prof_res.data['role']}"
        assert prof_res.data["company_id"] == TEST_COMPANY_ID
        print("  [OK] Trigger handle_new_user() verified for admin profile.")

        # 3. Admin Authentication and FastAPI Endpoints
        print("[3/7] Testing Admin Login and FastAPI Endpoints...")
        login_res = anon_supabase.auth.sign_in_with_password({
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASS
        })
        admin_token = login_res.session.access_token
        assert admin_token, "Failed to obtain admin token"

        # Test GET /api/auth/me
        me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert me_res.status_code == 200, f"GET /api/auth/me failed: {me_res.text}"
        me_data = me_res.json()
        assert me_data["role"] == "admin"
        assert me_data["company_id"] == TEST_COMPANY_ID
        print("  [OK] GET /api/auth/me verified for admin.")

        # Test GET /api/company
        comp_res = client.get("/api/company", headers={"Authorization": f"Bearer {admin_token}"})
        assert comp_res.status_code == 200, f"GET /api/company failed: {comp_res.text}"
        assert comp_res.json()["razon_social"] == "IAC Latam Test S.A.S."
        print("  [OK] GET /api/company verified under RLS.")

        # 4. User Invitation via POST /api/admin/invite-user
        print("[4/7] Testing Commercial User Invitation via Backend API...")
        invite_res = client.post(
            "/api/admin/invite-user",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": TEST_COMM_EMAIL,
                "nombre": "Carlos",
                "apellido": "Comercial",
                "cargo": "Asesor Senior de Ventas",
                "celular": "3119876543",
                "tipo_documento": "CC",
                "documento_identidad": "1098765432",
                "role": "commercial"
            }
        )
        assert invite_res.status_code == 200, f"POST /api/admin/invite-user failed: {invite_res.text}"
        invite_data = invite_res.json()
        assert invite_data["status"] == "success"
        comm_uid = invite_data["user_id"]
        created_user_ids.append(comm_uid)
        assert invite_data.get("activation_link") is not None or invite_data.get("message") is not None
        print(f"  [OK] User invited successfully. Activation link: {invite_data['activation_link'][:45]}...")

        # Verify commercial profile created in public.profiles with correct metadata
        comm_prof = admin_supabase.table("profiles").select("*").eq("id", comm_uid).single().execute()
        assert comm_prof.data["role"] == "commercial"
        assert comm_prof.data["cargo"] == "Asesor Senior de Ventas"
        assert comm_prof.data["company_id"] == TEST_COMPANY_ID
        print("  [OK] Trigger handle_new_user() verified for invited commercial profile.")

        # 5. Commercial User Activation, Login & RBAC checks
        print("[5/7] Testing Commercial User Login & RBAC Permissions...")
        # Simulate user setting password via activation link
        admin_supabase.auth.admin.update_user_by_id(comm_uid, {"password": TEST_COMM_PASS})

        comm_login_res = anon_supabase.auth.sign_in_with_password({
            "email": TEST_COMM_EMAIL,
            "password": TEST_COMM_PASS
        })
        comm_token = comm_login_res.session.access_token
        assert comm_token, "Failed to obtain commercial token"

        # Verify commercial user GET /api/auth/me
        comm_me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {comm_token}"})
        assert comm_me_res.status_code == 200
        assert comm_me_res.json()["role"] == "commercial"
        print("  [OK] GET /api/auth/me verified for commercial user.")

        # Verify RBAC: commercial user MUST NOT be allowed to invite users
        unauth_invite_res = client.post(
            "/api/admin/invite-user",
            headers={"Authorization": f"Bearer {comm_token}"},
            json={
                "email": "hack_attempt@iaclatam.com",
                "nombre": "Hacker",
                "apellido": "Test",
                "cargo": "Infiltrator",
                "celular": "3000000000"
            }
        )
        assert unauth_invite_res.status_code == 403, f"Expected 403 Forbidden for non-admin invite, got {unauth_invite_res.status_code}"
        print("  [OK] RBAC verified: Commercial user cannot invite users (403 Forbidden).")

        # 5b. Commercial User Privilege / Attribute Forgery Resistance (Requirement 7)
        print("[5b/7] Testing Commercial User Anti-Forgery Protection (Requirement 7)...")
        orig_comm = admin_supabase.table("profiles").select("*").eq("id", comm_uid).single().execute().data
        
        # User client attempts to forge attributes via GoTrue updateUser({ data: { ... } })
        # Using the commercial user's own token session:
        user_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        user_client.auth.set_session(access_token=comm_token, refresh_token=comm_login_res.session.refresh_token)
        user_client.auth.update_user({
            "data": {
                "cargo": "Director General Presidente",
                "documento_identidad": "9999999999",
                "role": "admin",
                "company_id": OTHER_COMPANY_ID,
                # Allowed fields to update:
                "nombre": "Carlos",
                "apellido": "Actualizado",
                "celular": "3119999999"
            }
        })

        # Verify public.profiles after updateUser()
        comm_after_update = admin_supabase.table("profiles").select("*").eq("id", comm_uid).single().execute().data
        # 4 Critical protected fields MUST BE 100% UNCHANGED
        assert comm_after_update["cargo"] == orig_comm["cargo"], f"Forgery leak! Cargo was changed from '{orig_comm['cargo']}' to '{comm_after_update['cargo']}'"
        assert comm_after_update["documento_identidad"] == orig_comm["documento_identidad"], f"Forgery leak! Doc ID was changed from '{orig_comm['documento_identidad']}' to '{comm_after_update['documento_identidad']}'"
        assert comm_after_update["role"] == orig_comm["role"], f"Privilege escalation! Role was changed from '{orig_comm['role']}' to '{comm_after_update['role']}'"
        assert comm_after_update["company_id"] == orig_comm["company_id"], f"Tenant escape! Company ID was changed from '{orig_comm['company_id']}' to '{comm_after_update['company_id']}'"
        
        # Allowed fields SHOULD have updated safely
        assert comm_after_update["apellido"] == "Actualizado"
        assert comm_after_update["celular"] == "3119999999"
        print("  [OK] Auth trigger immunity verified: updateUser({ cargo, documento_identidad, role, company_id }) resulted in ZERO changes to protected attributes, while allowed fields updated safely.")

        # Step B: Direct SQL / PostgREST modification attempt by commercial user
        direct_update_blocked = False
        try:
            user_client.table("profiles").update({"cargo": "Director General Presidente"}).eq("id", comm_uid).execute()
        except Exception as e:
            direct_update_blocked = True
            print(f"  [OK] Direct SQL UPDATE of cargo blocked by trigger/RLS: {type(e).__name__}")
        assert direct_update_blocked, "Security Failure: Commercial user was able to directly UPDATE their cargo via PostgREST!"

        # 6. Template Version & Form Fill Lifecycle with Storage Upload
        print("[6/7] Testing Template Lifecycle & Form Fill Storage Isolation...")
        # Insert test template
        admin_supabase.table("pdf_templates").insert({
            "id": TEST_TPL_ID,
            "company_id": TEST_COMPANY_ID,
            "codigo": "TPL-E2E-TEST",
            "nombre": "Formulario E2E de Prueba",
            "is_active": True
        }).execute()

        # Insert test template version (status = published)
        admin_supabase.table("pdf_template_versions").insert({
            "id": TEST_VER_ID,
            "template_id": TEST_TPL_ID,
            "version": 1,
            "filename": "test_e2e.pdf",
            "storage_path": "templates/test_e2e.pdf",
            "status": "published",
            "page_count": 1,
            "is_acroform": False,
            "is_active": True
        }).execute()
        print("  [OK] Published template version inserted.")

        # Start form fill as commercial user (using 'legal_rep_only' context)
        start_fill_res = client.post(
            "/api/form-fill/start",
            headers={"Authorization": f"Bearer {comm_token}"},
            json={
                "template_version_id": TEST_VER_ID,
                "commercial_profile_id": None, # legal_rep_only
                "metadata": {"form_title": "Test Licitacion IAC"}
            }
        )
        assert start_fill_res.status_code == 200, f"POST /api/form-fill/start failed: {start_fill_res.text}"
        history_id = start_fill_res.json()["history_id"]
        assert history_id is not None
        print(f"  [OK] Form fill started (History ID: {history_id}).")

        # Simulate generated PDF upload into Storage
        expected_storage_path = f"{TEST_COMPANY_ID}/{comm_uid}/{history_id}.pdf"
        dummy_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
        
        # Upload via admin client to simulate background PDF engine worker
        admin_supabase.storage.from_("generated-pdfs").upload(
            expected_storage_path,
            dummy_pdf,
            file_options={"content-type": "application/pdf"}
        )
        created_storage_paths.append(expected_storage_path)
        print(f"  [OK] Uploaded PDF to Storage: {expected_storage_path}")

        # Complete form fill
        complete_res = client.post(
            "/api/form-fill/complete",
            headers={"Authorization": f"Bearer {comm_token}"},
            json={
                "history_id": history_id,
                "output_storage_path": expected_storage_path,
                "metadata": {"total_placed": 5}
            }
        )
        assert complete_res.status_code == 200, f"POST /api/form-fill/complete failed: {complete_res.text}"
        assert complete_res.json()["status"] == "completed"
        print("  [OK] Form fill completed successfully.")

        # Request signed URL as the commercial owner
        signed_url_res = client.get(
            f"/api/form-fill/{history_id}/signed-url",
            headers={"Authorization": f"Bearer {comm_token}"}
        )
        assert signed_url_res.status_code == 200, f"GET signed-url failed: {signed_url_res.text}"
        signed_url_data = signed_url_res.json()
        assert "token=" in signed_url_data["signed_url"]
        print("  [OK] Signed URL successfully generated for document owner.")

        # Request signed URL as Admin (company audit privilege)
        admin_signed_res = client.get(
            f"/api/form-fill/{history_id}/signed-url",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert admin_signed_res.status_code == 200
        print("  [OK] Admin successfully retrieved signed URL for audit.")

        # 7. Cross-Company Isolation Verification
        print("[7/7] Verifying Cross-Tenant Isolation...")
        # Create second company and user
        admin_supabase.table("companies").insert({
            "id": OTHER_COMPANY_ID,
            "nit": "900000002",
            "dv": "2",
            "pais": "Colombia",
            "razon_social": "Competitor Corp S.A.S."
        }).execute()

        other_user_res = admin_supabase.auth.admin.create_user({
            "email": OTHER_USER_EMAIL,
            "password": OTHER_USER_PASS,
            "email_confirm": True,
            "app_metadata": {
                "company_id": OTHER_COMPANY_ID,
                "role": "commercial"
            },
            "user_metadata": {
                "nombre": "Other",
                "apellido": "User",
                "cargo": "Asesor Competidor",
                "celular": "3209876543"
            }
        })
        other_uid = other_user_res.user.id
        created_user_ids.append(other_uid)
        other_login = anon_supabase.auth.sign_in_with_password({
            "email": OTHER_USER_EMAIL,
            "password": OTHER_USER_PASS
        })
        other_token = other_login.session.access_token

        # Attempt to access Company 1's generated document with Company 2's token
        other_signed_res = client.get(
            f"/api/form-fill/{history_id}/signed-url",
            headers={"Authorization": f"Bearer {other_token}"}
        )
        assert other_signed_res.status_code == 404, f"Cross-tenant leak detected! Status: {other_signed_res.status_code}"
        print("  [OK] Cross-tenant isolation verified: Other company cannot access record (404 Not Found).")

        print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

    finally:
        print("\n=======================================================")
        print("TEARDOWN: Cleaning up test artifacts and users...")
        print("=======================================================")
        # Remove storage files
        try:
            if created_storage_paths:
                admin_supabase.storage.from_("generated-pdfs").remove(created_storage_paths)
                print(f"  [OK] Removed {len(created_storage_paths)} test files from Storage.")
        except Exception as e:
            print(f"  ! Error removing storage files: {e}")

        # Targeted deletion of test database records (must occur before deleting auth users to satisfy FK constraints)
        try:
            admin_supabase.table("form_fill_history").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("pdf_mappings").delete().eq("template_version_id", TEST_VER_ID).execute()
            admin_supabase.table("pdf_template_versions").delete().eq("id", TEST_VER_ID).execute()
            admin_supabase.table("pdf_templates").delete().eq("id", TEST_TPL_ID).execute()
            admin_supabase.table("legal_representatives").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("company_bank_accounts").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("profiles").delete().in_("company_id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            admin_supabase.table("companies").delete().in_("id", [TEST_COMPANY_ID, OTHER_COMPANY_ID]).execute()
            print("  [OK] Targeted database cleanup completed successfully.")
        except Exception as e:
            print(f"  ! Error during targeted cleanup: {e}")

        # Targeted deletion of test users in auth.users
        for uid in created_user_ids:
            try:
                admin_supabase.auth.admin.delete_user(uid)
                print(f"  [OK] Deleted test user {uid}.")
            except Exception as e:
                print(f"  ! Error deleting test user {uid}: {e}")

        # Verification: Assert all table row counts are strictly 0
        tables_to_check = [
            "companies",
            "profiles",
            "company_bank_accounts",
            "legal_representatives",
            "pdf_templates",
            "pdf_template_versions",
            "pdf_mappings",
            "form_fill_history"
        ]
        dirty = False
        for tbl in tables_to_check:
            count_res = admin_supabase.table(tbl).select("*", count="exact").execute()
            count = count_res.count or len(count_res.data)
            if count != 0:
                print(f"  [DIRTY] Table '{tbl}' has {count} remaining rows!")
                dirty = True
            else:
                print(f"  [OK] Table '{tbl}': 0 rows.")

        # Check storage
        storage_objs = admin_supabase.storage.from_("generated-pdfs").list()
        if len(storage_objs) > 0:
            print(f"  [DIRTY] Storage 'generated-pdfs' has {len(storage_objs)} remaining objects!")
            dirty = True
        else:
            print("  [OK] Storage 'generated-pdfs': 0 objects.")

        assert not dirty, "DATABASE IS NOT CLEAN! Row counts must be strictly zero."
        print("\nVERIFICATION CONFIRMED: All application tables and storage objects are strictly at ZERO rows.")

if __name__ == "__main__":
    run_controlled_e2e_test()
