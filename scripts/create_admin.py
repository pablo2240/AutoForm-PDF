"""Crea (o promueve) un perfil administrador en Supabase Auth + commercial_profiles.

Uso (desde la raiz del repo, con .env apuntando a la base objetivo):
    .venv\\Scripts\\python.exe scripts/create_admin.py correo@iaclatam.com "Nombre" "Apellido"

La contrasena se pide por consola (no se guarda ni se imprime).
"""
import getpass
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.auth_supabase import get_supabase_admin_client  # noqa: E402
from backend.db.auth import hash_password  # noqa: E402
from backend.db.models import CommercialProfile  # noqa: E402
from backend.db.session import SessionLocal  # noqa: E402


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    email = sys.argv[1].strip().lower()
    nombre, apellido = sys.argv[2].strip(), sys.argv[3].strip()
    password = getpass.getpass("Contrasena del admin (min. 8 caracteres): ")
    if len(password) < 8:
        sys.exit("Contrasena demasiado corta.")

    # 1. Supabase Auth: crear usuario con role=admin en app_metadata (o promover si ya existe)
    client = get_supabase_admin_client()
    user_id = None
    try:
        res = client.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "app_metadata": {"role": "admin"},
            "user_metadata": {"nombre": nombre, "apellido": apellido, "cargo": "Administrador"},
        })
        user_id = res.user.id
        print("Usuario creado en Supabase Auth.")
    except Exception as exc:
        print(f"Create fallo ({type(exc).__name__}); intentando promover usuario existente...")
        for u in client.auth.admin.list_users(page=1, per_page=1000):
            if (u.email or "").lower() == email:
                client.auth.admin.update_user_by_id(
                    u.id, {"password": password, "app_metadata": {"role": "admin"}}
                )
                user_id = u.id
                print("Usuario existente promovido a admin.")
                break
    if not user_id:
        sys.exit("No se pudo crear ni encontrar el usuario en Supabase Auth.")

    # 2. public.profiles (si existe y tiene trigger/tabla)
    try:
        client.table("profiles").upsert({"id": user_id, "role": "admin", "is_active": True}).execute()
    except Exception as exc:
        print(f"Aviso: no se actualizo public.profiles ({type(exc).__name__}).")

    # 3. commercial_profiles (BD relacional)
    db = SessionLocal()
    try:
        row = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(email)).first()
        if row:
            row.role, row.is_active = "admin", True
            row.password_hash = hash_password(password)
        else:
            db.add(CommercialProfile(
                id=str(user_id) or str(uuid.uuid4()),
                profile_name=f"{nombre} {apellido}",
                nombre=nombre, apellido=apellido, cargo="Administrador",
                email=email, celular="N/A", role="admin", is_active=True,
                password_hash=hash_password(password),
            ))
        db.commit()
    finally:
        db.close()
    print(f"Listo: {email} es administrador. Debe iniciar sesion de nuevo.")


if __name__ == "__main__":
    main()
