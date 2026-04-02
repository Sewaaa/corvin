"""
Sandbox — API endpoints.

POST   /sandbox/upload        Upload file per analisi statica
GET    /sandbox/              Lista file analizzati (con filtri)
GET    /sandbox/{id}          Dettaglio risultato analisi
DELETE /sandbox/{id}          Elimina file e record (admin)
"""
import os
import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin, get_current_org
from app.models.organization import Organization
from app.models.sandbox import FileStatus, SandboxFile
from app.models.user import User
from app.modules.sandbox.service import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    compute_hashes,
    ensure_upload_dir,
    get_stored_path,
)
from app.schemas.sandbox import SandboxListItem, SandboxResult, SandboxUploadResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_file_or_404(file_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> SandboxFile:
    result = await db.execute(
        select(SandboxFile).where(
            SandboxFile.id == file_id,
            SandboxFile.organization_id == org_id,
        )
    )
    f = result.scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="File non trovato")
    return f


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=SandboxUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Carica un file per l'analisi statica",
)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    """
    Accetta il file, valida dimensione e MIME type, salva con nome UUID,
    dispatcha il task Celery per l'analisi asincrona.

    Sicurezza:
    - Dimensione massima: `max_upload_size_mb` MB
    - MIME type validato prima della scrittura su disco
    - Filename originale salvato solo nel DB, non usato nel path
    """
    ensure_upload_dir()

    # Leggi in memoria per validare dimensione (evita scrittura parziale)
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File troppo grande. Massimo: {settings.max_upload_size_mb} MB",
        )
    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="File vuoto")

    # Validazione content-type dichiarato (non ci fidiamo del nome file)
    content_type = file.content_type or "application/octet-stream"
    # Normalizza content type (rimuove parametri tipo "; charset=utf-8")
    base_mime = content_type.split(";")[0].strip().lower()
    if base_mime not in ALLOWED_MIME_TYPES:
        logger.warning(
            "sandbox_rejected_mime",
            mime=base_mime,
            filename=file.filename,
            org_id=str(org.id),
        )
        raise HTTPException(
            status_code=415,
            detail=f"Tipo di file non supportato: {base_mime}",
        )

    # Hash pre-salvataggio per deduplicazione
    md5, sha256 = compute_hashes(file_data)

    # Deduplicazione: stesso file già presente per questa org?
    existing = await db.execute(
        select(SandboxFile).where(
            SandboxFile.organization_id == org.id,
            SandboxFile.sha256_hash == sha256,
        )
    )
    dup = existing.scalar_one_or_none()
    if dup:
        # Restituisce il record esistente senza ri-analizzare
        return dup

    # Salvataggio sicuro con nome UUID
    file_id = uuid.uuid4()
    original_filename = file.filename or "unknown"
    ext = os.path.splitext(original_filename)[1]
    stored_path = get_stored_path(file_id, ext)

    with open(stored_path, "wb") as f_out:
        f_out.write(file_data)

    sandbox_file = SandboxFile(
        id=file_id,
        organization_id=org.id,
        original_filename=original_filename[:512],
        stored_path=stored_path,
        file_size=len(file_data),
        mime_type=base_mime,
        md5_hash=md5,
        sha256_hash=sha256,
        submitted_by=current_user.id,
        status=FileStatus.PENDING,
    )
    db.add(sandbox_file)
    await db.commit()
    await db.refresh(sandbox_file)

    from app.modules.sandbox.tasks import analyze_file_task
    analyze_file_task.delay(str(sandbox_file.id))

    logger.info(
        "sandbox_file_uploaded",
        file_id=str(file_id),
        filename=original_filename,
        size=len(file_data),
        sha256=sha256[:16],
        org_id=str(org.id),
    )
    return sandbox_file


@router.get(
    "/",
    response_model=List[SandboxListItem],
    summary="Lista file nel sandbox",
)
async def list_files(
    status_filter: Optional[FileStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    query = select(SandboxFile).where(SandboxFile.organization_id == org.id)
    if status_filter:
        query = query.where(SandboxFile.status == status_filter)
    query = query.order_by(SandboxFile.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/{file_id}",
    response_model=SandboxResult,
    summary="Dettaglio analisi file",
)
async def get_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    return await _get_file_or_404(file_id, org.id, db)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina file e record di analisi",
    dependencies=[Depends(require_admin)],
)
async def delete_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    sandbox_file = await _get_file_or_404(file_id, org.id, db)

    # Rimozione file da disco (best-effort — non fa fallire la richiesta)
    try:
        if os.path.exists(sandbox_file.stored_path):
            os.remove(sandbox_file.stored_path)
    except OSError as exc:
        logger.warning("sandbox_file_delete_failed", path=sandbox_file.stored_path, error=str(exc))

    await db.delete(sandbox_file)
    await db.commit()
