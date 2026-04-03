"""
Reports — service layer.

aggregate_summary(): aggrega statistiche da tutti i moduli per un'organizzazione.
generate_pdf_report(): produce un PDF executive report con reportlab.
"""
import io
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.breach import BreachRecord, MonitoredEmail
from app.models.domain import Domain
from app.models.email_account import EmailAccount
from app.models.email_threat import EmailThreat
from app.models.notification import Notification, NotificationSeverity
from app.models.sandbox import SandboxFile, FileStatus
from app.models.web_scan import ScanFinding, ScanStatus, WebScan

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data aggregation
# ---------------------------------------------------------------------------

async def aggregate_summary(db: AsyncSession, organization_id: UUID) -> Dict[str, Any]:
    """
    Aggrega statistiche da tutti i moduli per l'organizzazione.
    Restituisce un dict strutturato per modulo, usato sia dall'API JSON
    che dal generatore PDF.
    """
    org_id = organization_id

    # ---- Breach Monitor ----
    total_emails = await _count(db, MonitoredEmail, org_id)
    breached_emails = await _count(db, MonitoredEmail, org_id, MonitoredEmail.is_breached == True)  # noqa: E712
    total_breach_records = await _count(db, BreachRecord, org_id)

    # ---- Domain Reputation ----
    total_domains = await _count(db, Domain, org_id)
    verified_domains = await _count(db, Domain, org_id, Domain.is_verified == True)  # noqa: E712
    avg_score_result = await db.execute(
        select(func.avg(Domain.reputation_score)).where(
            Domain.organization_id == org_id,
            Domain.reputation_score.isnot(None),
        )
    )
    avg_score = avg_score_result.scalar_one_or_none()

    # ---- Web Scanner ----
    total_scans = await _count(db, WebScan, org_id)
    completed_scans = await _count(db, WebScan, org_id, WebScan.status == ScanStatus.COMPLETED)
    # Findings per severity
    findings_by_sev = {}
    for sev in ("critical", "high", "medium", "low", "info"):
        count = await db.execute(
            select(func.count(ScanFinding.id))
            .join(WebScan, ScanFinding.scan_id == WebScan.id)
            .where(
                WebScan.organization_id == org_id,
                ScanFinding.severity == sev,
            )
        )
        findings_by_sev[sev] = count.scalar_one()

    # ---- Email Protection ----
    total_email_accounts = await _count(db, EmailAccount, org_id)
    total_email_threats = await _count(db, EmailThreat, org_id)
    critical_threats = await _count(db, EmailThreat, org_id, EmailThreat.severity == "critical")
    quarantined = await _count(db, EmailThreat, org_id, EmailThreat.is_quarantined == True)  # noqa: E712

    # ---- File Sandbox ----
    total_files = await _count(db, SandboxFile, org_id)
    files_by_status = {}
    for st in FileStatus:
        c = await _count(db, SandboxFile, org_id, SandboxFile.status == st)
        files_by_status[st.value] = c

    # ---- Notifications ----
    total_notifs = await _count(db, Notification, org_id)
    unread_notifs = await _count(db, Notification, org_id, Notification.is_read == False)  # noqa: E712
    notifs_by_sev = {}
    for sev in NotificationSeverity:
        c = await _count(db, Notification, org_id, Notification.severity == sev)
        notifs_by_sev[sev.value] = c

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "organization_id": str(org_id),
        "breach_monitor": {
            "monitored_emails": total_emails,
            "breached_emails": breached_emails,
            "total_breach_records": total_breach_records,
            "breach_rate_pct": round(breached_emails / total_emails * 100, 1) if total_emails else 0,
        },
        "domain_reputation": {
            "total_domains": total_domains,
            "verified_domains": verified_domains,
            "average_score": round(float(avg_score), 1) if avg_score else None,
        },
        "web_scanner": {
            "total_scans": total_scans,
            "completed_scans": completed_scans,
            "findings_by_severity": findings_by_sev,
            "total_findings": sum(findings_by_sev.values()),
        },
        "email_protection": {
            "monitored_accounts": total_email_accounts,
            "total_threats": total_email_threats,
            "critical_threats": critical_threats,
            "quarantined": quarantined,
        },
        "file_sandbox": {
            "total_files": total_files,
            "by_status": files_by_status,
        },
        "notifications": {
            "total": total_notifs,
            "unread": unread_notifs,
            "by_severity": notifs_by_sev,
        },
    }


async def _count(db, model, org_id, *conditions):
    """Helper: COUNT con organization_id filter + condizioni opzionali."""
    q = select(func.count(model.id)).where(model.organization_id == org_id)
    for cond in conditions:
        q = q.where(cond)
    result = await db.execute(q)
    return result.scalar_one()


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_pdf_report(summary: Dict[str, Any], org_name: str) -> bytes:
    """
    Genera un PDF executive report dal dict summary.
    Restituisce i byte del PDF pronto per lo streaming HTTP.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    PURPLE = colors.HexColor("#7c3aed")
    DARK_BG = colors.HexColor("#1a1a2e")
    GRAY = colors.HexColor("#9ca3af")

    style_title = ParagraphStyle(
        "CorvinTitle", parent=styles["Title"],
        textColor=PURPLE, fontSize=24, spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "CorvinSub", parent=styles["Normal"],
        textColor=GRAY, fontSize=10, spaceAfter=16,
    )
    style_h2 = ParagraphStyle(
        "CorvinH2", parent=styles["Heading2"],
        textColor=PURPLE, fontSize=13, spaceBefore=18, spaceAfter=6,
    )
    style_body = ParagraphStyle(
        "CorvinBody", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#374151"),
    )

    generated_at = summary.get("generated_at", "")[:19].replace("T", " ")

    def section_table(rows, col_widths=None):
        data = [["Metrica", "Valore"]] + [[str(k), str(v)] for k, v in rows]
        t = Table(data, colWidths=col_widths or [10 * cm, 6 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#374151")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ROWPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        return t

    elements = []

    # ---- Header ----
    elements.append(Paragraph("Corvin Security Platform", style_title))
    elements.append(Paragraph("Executive Security Report", style_subtitle))
    elements.append(Paragraph(f"Organizzazione: <b>{org_name}</b>", style_body))
    elements.append(Paragraph(f"Generato il: {generated_at} UTC", style_body))
    elements.append(Spacer(1, 0.4 * cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=PURPLE))
    elements.append(Spacer(1, 0.3 * cm))

    # ---- Breach Monitor ----
    bm = summary["breach_monitor"]
    elements.append(Paragraph("Breach Monitor", style_h2))
    elements.append(section_table([
        ("Email monitorate", bm["monitored_emails"]),
        ("Email compromesse", bm["breached_emails"]),
        ("Breach rate", f"{bm['breach_rate_pct']}%"),
        ("Breach records totali", bm["total_breach_records"]),
    ]))

    # ---- Domain Reputation ----
    dr = summary["domain_reputation"]
    elements.append(Paragraph("Domain Reputation", style_h2))
    elements.append(section_table([
        ("Domini monitorati", dr["total_domains"]),
        ("Domini verificati", dr["verified_domains"]),
        ("Punteggio medio", dr["average_score"] if dr["average_score"] else "—"),
    ]))

    # ---- Web Scanner ----
    ws = summary["web_scanner"]
    findings = ws["findings_by_severity"]
    elements.append(Paragraph("Web Scanner", style_h2))
    elements.append(section_table([
        ("Scansioni totali", ws["total_scans"]),
        ("Scansioni completate", ws["completed_scans"]),
        ("Finding totali", ws["total_findings"]),
        ("Finding critici", findings.get("critical", 0)),
        ("Finding alti", findings.get("high", 0)),
        ("Finding medi", findings.get("medium", 0)),
    ]))

    # ---- Email Protection ----
    ep = summary["email_protection"]
    elements.append(Paragraph("Email Protection", style_h2))
    elements.append(section_table([
        ("Account monitorati", ep["monitored_accounts"]),
        ("Minacce rilevate", ep["total_threats"]),
        ("Minacce critiche", ep["critical_threats"]),
        ("Email in quarantena", ep["quarantined"]),
    ]))

    # ---- File Sandbox ----
    sb = summary["file_sandbox"]
    st = sb["by_status"]
    elements.append(Paragraph("File Sandbox", style_h2))
    elements.append(section_table([
        ("File analizzati", sb["total_files"]),
        ("Safe", st.get("safe", 0)),
        ("Suspicious", st.get("suspicious", 0)),
        ("Malicious", st.get("malicious", 0)),
        ("In analisi / Pending", st.get("analyzing", 0) + st.get("pending", 0)),
    ]))

    # ---- Notifications ----
    nt = summary["notifications"]
    sev = nt["by_severity"]
    elements.append(Paragraph("Notifications", style_h2))
    elements.append(section_table([
        ("Notifiche totali", nt["total"]),
        ("Non lette", nt["unread"]),
        ("Critical", sev.get("critical", 0)),
        ("High", sev.get("high", 0)),
        ("Medium", sev.get("medium", 0)),
    ]))

    # ---- Footer ----
    elements.append(Spacer(1, 0.6 * cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph(
        "Corvin Security Platform — Silent guardian for your digital perimeter.",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=7, textColor=GRAY),
    ))

    doc.build(elements)
    return buf.getvalue()
