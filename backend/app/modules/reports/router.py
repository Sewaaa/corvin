"""
Reports — API endpoints.

GET /reports/summary   JSON aggregato da tutti i moduli
GET /reports/pdf       PDF executive report (streaming response)
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_org
from app.models.organization import Organization
from app.models.user import User
from app.modules.reports.service import aggregate_summary, generate_pdf_report

router = APIRouter()


@router.get(
    "/summary",
    summary="Report JSON aggregato da tutti i moduli",
)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    return await aggregate_summary(db, org.id)


@router.get(
    "/pdf",
    summary="Genera e scarica il report PDF executive",
    response_class=StreamingResponse,
)
async def download_pdf(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    summary = await aggregate_summary(db, org.id)
    pdf_bytes = generate_pdf_report(summary, org.name)

    from datetime import datetime, timezone
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"corvin-report-{date_str}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
