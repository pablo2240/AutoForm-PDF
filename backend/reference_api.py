"""Admin API for the reference library (knowledge layer). Thin wrapper over ReferenceLibrary."""

import os
import tempfile
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.auth_supabase import require_admin
from backend.pdf_filling_agent.reference_library import ReferenceLibrary, get_default_library

router = APIRouter(prefix="/api/reference-library", tags=["reference-library"])
MAX_PDF_BYTES = 25 * 1024 * 1024


def _lib() -> ReferenceLibrary:
    lib = get_default_library()
    if lib is None:
        raise HTTPException(status_code=503, detail="Biblioteca de referencias deshabilitada o no disponible")
    return lib


async def _read_pdf(file: UploadFile) -> bytes:
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="El archivo no es un PDF válido")
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF demasiado grande (máx. 25 MB)")
    return data


@router.get("")
def status(admin: Dict[str, Any] = Depends(require_admin)):
    return _lib().status()


@router.post("/sync")
def sync(force: bool = False, admin: Dict[str, Any] = Depends(require_admin)):
    return _lib().sync(force=force)


@router.post("/documents")
async def add_document(
    file: UploadFile = File(...),
    family: Optional[str] = Form(None),
    admin: Dict[str, Any] = Depends(require_admin),
):
    data = await _read_pdf(file)
    try:
        return _lib().add_document(file.filename or "referencia.pdf", data, family)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.delete("/documents/{doc_id:path}")
def remove_document(doc_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    try:
        if not _lib().remove_document(doc_id):
            raise HTTPException(status_code=404, detail="Referencia no encontrada")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return {"status": "success", "removed": doc_id}


@router.post("/documents/{doc_id:path}/reprocess")
def reprocess_document(doc_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    try:
        return _lib().reprocess(doc_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Referencia no encontrada")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get("/search")
def search(
    q: str,
    top_k: int = 5,
    family: Optional[str] = None,
    admin: Dict[str, Any] = Depends(require_admin),
):
    return {"query": q, "results": _lib().search(q, top_k=max(1, min(top_k, 25)), family=family)}


@router.post("/classify")
async def classify(file: UploadFile = File(...), admin: Dict[str, Any] = Depends(require_admin)):
    data = await _read_pdf(file)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return _lib().classify_pdf(path).to_dict()
    finally:
        os.remove(path)
