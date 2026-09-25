import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_requirements_contains_runtime_dependencies():
    req_file = PROJECT_ROOT / "requirements.txt"
    assert req_file.exists(), "requirements.txt must exist"

    content = req_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    supabase_entry = [l for l in lines if l.startswith("supabase")]
    pyjwt_entry = [l for l in lines if l.startswith("pyjwt[crypto]")]

    assert len(supabase_entry) == 1, "requirements.txt must include supabase"
    assert len(pyjwt_entry) == 1, "requirements.txt must include pyjwt[crypto]"

    assert ">=" in supabase_entry[0], "supabase must have a minimum version specification"
    assert ">=" in pyjwt_entry[0], "pyjwt[crypto] must have a minimum version specification"

def test_pyproject_toml_contains_runtime_dependencies():
    pyproject_file = PROJECT_ROOT / "pyproject.toml"
    assert pyproject_file.exists(), "pyproject.toml must exist"

    content = pyproject_file.read_text(encoding="utf-8")
    assert "supabase>=" in content, "pyproject.toml dependencies must include supabase"
    assert "pyjwt[crypto]>=" in content, "pyproject.toml dependencies must include pyjwt[crypto]"

def test_runtime_dependencies_importable():
    # Verify supabase client import
    from supabase import create_client, Client
    assert callable(create_client)
    assert Client is not None

    # Verify PyJWT with cryptographic algorithms
    import jwt
    from jwt import PyJWKClient
    assert callable(PyJWKClient)
    assert hasattr(jwt, "decode")

def test_frontend_api_config_node_test_suite():
    frontend_dir = PROJECT_ROOT / "frontend"
    result = subprocess.run(
        ["npm", "test"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
        shell=True
    )
    assert result.returncode == 0, f"npm test in frontend failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "Production build rejects missing or empty VITE_API_URL" in result.stdout
    assert "Production build rejects localhost and 127.0.0.1" in result.stdout
    assert "Production build rejects non-HTTPS URLs" in result.stdout
    assert "Production build accepts valid HTTPS URL" in result.stdout
    assert "Development mode permits localhost and defaults cleanly" in result.stdout
