from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path("/Users/macbook/Projects/OMMS")
OUTPUT_DIR = ROOT / "docs" / "training"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
GENERATED_ON = "May 20, 2026"

FOREST = colors.HexColor("#064E3B")
MINT = colors.HexColor("#EAF7F1")
BORDER = colors.HexColor("#D8E7DF")
TEXT = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#4B635A")
WARNING = colors.HexColor("#B45309")


@dataclass(frozen=True)
class Guide:
    filename: str
    title: str
    audience: str
    purpose: str
    screenshots: tuple[tuple[str, str], ...]
    sections: tuple[tuple[str, tuple[str, ...]], ...]
    checklist: tuple[str, ...]


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        alignment=TA_CENTER,
        textColor=FOREST,
        spaceAfter=18,
    )
)
styles.add(
    ParagraphStyle(
        name="GuideSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=MUTED,
        spaceAfter=18,
    )
)
styles.add(
    ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=20,
        textColor=FOREST,
        spaceBefore=12,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        textColor=TEXT,
        spaceAfter=7,
    )
)
styles.add(
    ParagraphStyle(
        name="Small",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        textColor=MUTED,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Callout",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        textColor=FOREST,
        backColor=MINT,
        borderColor=BORDER,
        borderWidth=0.6,
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=10,
    )
)


def bullet_list(items: tuple[str, ...]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, styles["Body"]), leftIndent=12) for item in items],
        bulletType="bullet",
        leftIndent=14,
        bulletFontName="Helvetica-Bold",
        bulletColor=FOREST,
    )


def screenshot(name: str, caption: str) -> list:
    path = SCREENSHOT_DIR / name
    if not path.exists():
        return [Paragraph(f"Screenshot unavailable: {name}", styles["Small"])]
    max_width = 6.6 * inch
    max_height = 3.8 * inch if name.startswith("web-") else 5.1 * inch
    image = Image(str(path))
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    return [
        Spacer(1, 6),
        image,
        Paragraph(caption, styles["Small"]),
        Spacer(1, 8),
    ]


def section(title: str, paragraphs: tuple[str, ...]) -> list:
    story = [Paragraph(title, styles["SectionTitle"])]
    for paragraph in paragraphs:
        if paragraph.startswith("Checklist:"):
            story.append(Paragraph(paragraph.replace("Checklist:", "").strip(), styles["Callout"]))
        elif paragraph.startswith("- "):
            story.append(bullet_list(tuple(item[2:] for item in paragraphs if item.startswith("- "))))
            break
        else:
            story.append(Paragraph(paragraph, styles["Body"]))
    return story


def cover(guide: Guide) -> list:
    meta = [
        ["Audience", guide.audience],
        ["Updated", GENERATED_ON],
        ["System", "OMMS Outdoor Media Management System"],
    ]
    table = Table(meta, colWidths=[1.35 * inch, 4.9 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), MINT),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("TEXTCOLOR", (0, 0), (0, -1), FOREST),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [
        Spacer(1, 0.5 * inch),
        Paragraph("VistaAi OMMS", styles["GuideSubtitle"]),
        Paragraph(guide.title, styles["CoverTitle"]),
        Paragraph(guide.purpose, styles["GuideSubtitle"]),
        Spacer(1, 0.2 * inch),
        table,
        Spacer(1, 0.4 * inch),
        Paragraph(
            "This guide reflects the current OMMS SaaS web platform and mobile operations companion: white and forest green UI, operational intelligence, role dashboards, alerts, imports/exports, POE review, billing risk, and system diagnostics.",
            styles["Callout"],
        ),
        PageBreak(),
    ]


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.6 * inch, 0.35 * inch, f"OMMS Training - {GENERATED_ON}")
    canvas.drawRightString(A4[0] - 0.6 * inch, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build(guide: Guide) -> None:
    doc = SimpleDocTemplate(
        str(OUTPUT_DIR / guide.filename),
        pagesize=A4,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=guide.title,
        author="VistaAi OMMS",
    )
    story = cover(guide)
    story.append(Paragraph("How to use this guide", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Use the screenshots as orientation, then follow the workflow sections in order. OMMS is role-aware, so users may see a smaller dashboard than the admin examples shown here.",
            styles["Body"],
        )
    )
    for shot, caption in guide.screenshots:
        story.extend(screenshot(shot, caption))
    for title, paragraphs in guide.sections:
        story.extend(section(title, paragraphs))
    story.append(Paragraph("Operational checklist", styles["SectionTitle"]))
    story.append(bullet_list(guide.checklist))
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)


GUIDES: tuple[Guide, ...] = (
    Guide(
        filename="OMMS_Master_Training_Manual.pdf",
        title="OMMS Master Training Manual",
        audience="All OMMS users",
        purpose="A complete onboarding handbook for the OMMS lifecycle, terminology, dashboards, mobile field workflow, and operational controls.",
        screenshots=(
            ("web-dashboard.png", "Role-aware dashboard with campaign, billing, inventory, and action widgets."),
            ("web-operations.png", "Operations intelligence cockpit with live monitoring, filters, system status, and import/export workbench."),
            ("web-billing.png", "Billing workspace for invoice status, overdue risk, payment collection, and statements."),
            ("mobile-admin-dashboard.png", "Mobile admin summary for high-level operational visibility."),
        ),
        sections=(
            ("OMMS operating model", (
                "OMMS manages outdoor media from inventory and campaign planning through booking, execution, POE review, billing, reporting, and alerts.",
                "The web SaaS platform is the source of truth for operational workflows, permissions, dashboards, and review controls. The mobile app is the field operations companion for assigned work and proof submission.",
            )),
            ("Core lifecycle", (
                "- Create or import inventory sites and media units.",
                "- Build campaign estimates, confirm bookings, and track execution.",
                "- Field staff upload POE with photo proof and GPS context.",
                "- Operations review POE, manage suspicious proofs, and monitor SLA risk.",
                "- Finance issues invoices, records payments, and tracks overdue escalation.",
                "- Admins monitor alerts, diagnostics, audit activity, imports, exports, and role dashboards.",
            )),
            ("Safety principles", (
                "Tenant and company scoping protect operational data. Finance and billing views stay permission controlled, and client or field roles do not receive operational intelligence that is outside their role.",
                "Imports use staged preview and explicit confirmation before inventory records are committed. Exports and imports run as background jobs with audit trails and notifications.",
            )),
        ),
        checklist=(
            "Confirm the user has the correct role before training.",
            "Use the dashboard first, then drill into modules only when the KPI indicates action.",
            "Treat alerts, SLA breaches, failed jobs, and overdue invoices as daily operational review items.",
            "Use Training Center PDFs as controlled reference material for onboarding.",
        ),
    ),
    Guide(
        filename="OMMS_Admin_Super_Admin_Guide.pdf",
        title="Admin Guide",
        audience="Owners, super admins, and system administrators",
        purpose="Administrative operating procedures for users, permissions, dashboard customization, diagnostics, maintenance mode, and controlled platform governance.",
        screenshots=(
            ("web-dashboard.png", "Admin dashboard with role-based widgets and operational summaries."),
            ("web-operations.png", "Operations cockpit for system health, alerts, imports, exports, and diagnostics."),
            ("web-training-center.png", "Protected Training Center with role-aware PDF access."),
        ),
        sections=(
            ("Admin responsibilities", (
                "Admins maintain the operational structure of OMMS: users, companies, permissions, diagnostics, training access, dashboard profiles, and controlled environment mode.",
                "Use Operations for platform health and incident visibility. Use role-based dashboards to keep each user group focused on the work they should see.",
            )),
            ("Dashboard customization", (
                "- Review the role-default widgets before changing a user dashboard.",
                "- Keep required health and alert widgets active for back-office roles.",
                "- Hide optional finance widgets only when the role does not need them.",
                "- Restore defaults when a dashboard becomes too narrow or misses important operating signals.",
            )),
            ("System diagnostics and maintenance", (
                "The System Status panel exposes safe non-secret state: API health, database connectivity, Redis/Celery configuration, failed requests, failed jobs, environment mode, and last successful import/export.",
                "Use maintenance or read-only mode during deployments, migrations, or incidents. Login and safe reads remain available; risky writes are blocked conservatively.",
            )),
        ),
        checklist=(
            "Verify roles before adding finance, operations, or admin access.",
            "Review alerts and audit timeline daily.",
            "Confirm imports and exports complete before relying on their output.",
            "Use maintenance/read-only mode only for controlled operational windows.",
        ),
    ),
    Guide(
        filename="OMMS_Operations_Team_Guide.pdf",
        title="Operations Guide",
        audience="Operations managers and coordinators",
        purpose="Daily operations playbook for campaign execution, POE review, alerts, jobs, imports, exports, and SLA management.",
        screenshots=(
            ("web-operations.png", "Operations intelligence with live summary, filters, KPIs, and job monitoring."),
            ("web-campaigns.png", "Campaign workspace showing campaign risk and performance context."),
            ("web-poe-review.png", "POE review queue for proof inspection and SLA decisions."),
        ),
        sections=(
            ("Daily operations rhythm", (
                "Start in Operations. Review live KPIs, alert severity, active import/export jobs, POE SLA warnings, POE breaches, suspicious proofs, and campaign risk.",
                "Use the global operational search and filters to move quickly from a risk signal to the affected campaign, POE, invoice, job, or audit event.",
            )),
            ("POE handling", (
                "- Review pending and suspicious POEs before SLA breach.",
                "- Prioritize suspicious unresolved proofs and oldest pending reviews.",
                "- Approve only when media, site, date, unit, and GPS context are acceptable.",
                "- Reject or request rework when the proof is incomplete, mismatched, or outside tolerance.",
            )),
            ("Jobs and retries", (
                "Imports and exports run in the background. Failed jobs can be retried only when eligible, preserving idempotency and avoiding duplicate inventory or reports.",
                "Use audit events and notifications to confirm who initiated a retry and whether it completed successfully.",
            )),
        ),
        checklist=(
            "Check POE SLA warning and breach counts.",
            "Review failed import/export jobs and retry only after understanding the failure.",
            "Use filters instead of exporting raw logs for daily review.",
            "Escalate critical campaign risk before the campaign end date.",
        ),
    ),
    Guide(
        filename="OMMS_Finance_Team_Guide.pdf",
        title="Finance Guide",
        audience="Finance and accounts teams",
        purpose="Finance operating guide for estimates, invoices, payments, overdue escalation, collection efficiency, and finance-safe dashboards.",
        screenshots=(
            ("web-billing.png", "Billing workspace with invoice status, overdue risk, and collection information."),
            ("web-dashboard.png", "Role dashboard with finance widgets when authorized."),
            ("web-operations.png", "Operations billing intelligence where finance or admin access is available."),
        ),
        sections=(
            ("Estimate to invoice workflow", (
                "OMMS connects campaign value, bookings, invoice generation, payment recording, and collection analytics. Finance users should work from approved estimates and issued invoices rather than ad hoc spreadsheets.",
                "Invoice/payment analytics are permission controlled and should not be exposed to field or client users unless business policy explicitly allows it.",
            )),
            ("Overdue escalation", (
                "- Monitor overdue count, overdue value, and age buckets.",
                "- Review largest overdue clients and critical overdue invoices first.",
                "- Use payment trend and collection efficiency to evaluate weekly cash flow risk.",
                "- Coordinate with operations when billing risk is linked to POE or campaign completion issues.",
            )),
            ("Collection efficiency", (
                "Collection efficiency compares collected amount against invoiced amount. Use it with overdue value and average days to payment to understand whether revenue is moving as expected.",
            )),
        ),
        checklist=(
            "Review overdue warning, breach, and critical status daily.",
            "Record payments promptly to keep dashboard metrics accurate.",
            "Do not share finance dashboards with non-finance field roles.",
            "Use alerts and notifications to track repeated billing risk.",
        ),
    ),
    Guide(
        filename="OMMS_Field_Staff_Training_Guide.pdf",
        title="Field Staff Guide",
        audience="Field staff and execution teams",
        purpose="Mobile-first guide for assigned work, site detail review, photo proof capture, GPS readiness, and upload status.",
        screenshots=(
            ("mobile-login.png", "Mobile login for field operations access."),
            ("mobile-poe-upload.png", "POE upload screen with site details, GPS readiness, and proof submission."),
            ("mobile-admin-dashboard.png", "Admin mobile summary, shown only to authorized admin users."),
        ),
        sections=(
            ("Mobile workflow", (
                "Field staff use the OMMS mobile app to view assigned work, confirm site context, capture or select proof media, attach GPS context, and submit POE for review.",
                "The mobile app follows the web platform language: assigned work, POE upload, GPS ready, upload status, suspicious/rework indicators, and task alerts.",
            )),
            ("POE submission standards", (
                "- Confirm the campaign and media unit before uploading.",
                "- Capture clear photo proof with the display visible.",
                "- Wait for GPS readiness when available.",
                "- Submit once and watch the upload status.",
                "- If read-only or maintenance mode is active, wait for operations to reopen submissions.",
            )),
            ("After submission", (
                "Operations will approve, reject, or request rework. If a proof is rejected or marked suspicious, follow the rework instructions and submit a corrected proof.",
            )),
        ),
        checklist=(
            "Verify the assigned site before travel or proof capture.",
            "Keep the phone location service enabled for GPS context.",
            "Do not upload unrelated or duplicate photos.",
            "Report blockers through the assigned work/status flow.",
        ),
    ),
    Guide(
        filename="OMMS_Inventory_Management_Guide.pdf",
        title="Inventory Import Guide",
        audience="Inventory managers and operations admins",
        purpose="Safe staged inventory onboarding guide for Excel/CSV templates, validation preview, confirmation, background import, and results review.",
        screenshots=(
            ("web-operations.png", "Operations Import / Export workbench and job monitoring."),
            ("web-dashboard.png", "Dashboard signals that help validate inventory readiness."),
        ),
        sections=(
            ("Template-first import", (
                "Download the Excel template from Operations before preparing inventory. Required site fields are site_code, site_name, site_type, address, city, and state.",
                "Latitude and longitude are optional because OMMS can capture GPS from the first verified POE. Unit code, dimensions, rate, and status are also optional when the source data is incomplete.",
            )),
            ("Preview before commit", (
                "- Upload CSV or Excel to generate validation preview.",
                "- Review valid, warning, failed, and duplicate row counts.",
                "- Fix missing required fields, invalid pricing, invalid dimensions, repeated site/unit codes, and suspicious coordinates.",
                "- Confirm only when the preview is acceptable.",
            )),
            ("Background processing", (
                "Confirmed imports run as background jobs. OMMS tracks progress, partial success, skipped rows, failed rows, audit events, and completion notifications.",
            )),
        ),
        checklist=(
            "Always download the latest import template.",
            "Never assume preview saved inventory records.",
            "Confirm import only after duplicate and warning review.",
            "Download or inspect failure reports after completion.",
        ),
    ),
    Guide(
        filename="OMMS_POE_Review_Guide.pdf",
        title="POE Review Guide",
        audience="Operations reviewers and admins",
        purpose="Detailed POE review and SLA guide for proof media, suspicious handling, reviewer workload, badges, and approval decisions.",
        screenshots=(
            ("web-poe-review.png", "POE review queue and proof review interface."),
            ("web-operations.png", "Operations POE SLA and suspicious proof indicators."),
            ("mobile-poe-upload.png", "Mobile POE upload source workflow for field staff."),
        ),
        sections=(
            ("Review standards", (
                "POE review validates that the proof belongs to the right campaign, site, media unit, execution date, and location context. Reviewers should be consistent and document exceptions clearly.",
                "SLA indicators warn after 24 hours for pending reviews and breach after 48 hours. Suspicious POEs warn after 12 hours and breach after 24 hours.",
            )),
            ("Approve, reject, or rework", (
                "- Approve when proof media and metadata are consistent.",
                "- Reject when proof is invalid, unrelated, missing, or materially wrong.",
                "- Request rework when the issue can be corrected by field staff.",
                "- Escalate suspicious unresolved proofs before SLA breach.",
            )),
            ("Workload balancing", (
                "Use reviewer workload and unassigned backlog to prevent delayed approvals. Overloaded reviewers or large unassigned queues should be redistributed by operations leads.",
            )),
        ),
        checklist=(
            "Review oldest pending and suspicious proofs first.",
            "Check campaign, unit, media, date/time, location, and notes.",
            "Use consistent rejection or rework reasons.",
            "Watch SLA breach counts in Operations.",
        ),
    ),
    Guide(
        filename="OMMS_Dashboard_Alerts_Guide.pdf",
        title="Dashboard & Alerts Guide",
        audience="Admins, owners, operations, and finance leads",
        purpose="Guide to role dashboards, live Operations, alert severity, acknowledgement, cooldowns, saved views, search, and system status.",
        screenshots=(
            ("web-dashboard.png", "Role-based dashboard with compact business and operations widgets."),
            ("web-operations.png", "Live Operations dashboard with search, filters, alerts, diagnostics, and activity."),
            ("web-training-center.png", "Training Center access to controlled reference material."),
        ),
        sections=(
            ("Live operations layer", (
                "Operations refreshes key data without requiring a page reload. Live indicators show updated time, active jobs, export activity, alerts, and system status calmly.",
                "Widget-level failures are contained so one unavailable feed does not hide the full dashboard.",
            )),
            ("Alerts and saved views", (
                "- Use alert severity to prioritize admin attention.",
                "- Acknowledge alerts when responsibility is accepted.",
                "- Cooldowns prevent duplicate alert spam.",
                "- Save recurring views such as Critical Campaigns, Pending POEs, Failed Imports, or Finance Risk.",
            )),
            ("System status", (
                "System Status reports API, database, Redis/Celery readiness, failed requests, slow requests, failed jobs, last import/export, deployment environment, and maintenance mode without exposing secrets.",
            )),
        ),
        checklist=(
            "Review critical alerts before normal dashboard widgets.",
            "Use saved views for repeated daily operating reviews.",
            "Treat degraded system health as an admin follow-up item.",
            "Keep role dashboard widgets aligned with each user's responsibilities.",
        ),
    ),
    Guide(
        filename="OMMS_Mobile_App_Quick_Start_Guide.pdf",
        title="Mobile App Quick Start Guide",
        audience="Field staff, operations leads, and mobile admins",
        purpose="Quick start for the OMMS mobile operations companion, including login, assigned work, POE upload, status, alerts, and admin summary.",
        screenshots=(
            ("mobile-login.png", "Secure mobile sign-in."),
            ("mobile-poe-upload.png", "Field POE upload with GPS and photo readiness."),
            ("mobile-admin-dashboard.png", "Mobile admin high-level operations summary."),
        ),
        sections=(
            ("First login", (
                "Use the OMMS account issued by your admin. The mobile app uses the same operational terminology as the web platform and shows role-appropriate information.",
                "Field users see assigned work and POE tasks. Admin users may see compact campaign, POE SLA, billing risk, alert, and system status summaries.",
            )),
            ("Assigned work and POE upload", (
                "- Open assigned work and confirm campaign/site details.",
                "- Capture or select proof media.",
                "- Wait for GPS ready status where available.",
                "- Submit proof and watch upload progress.",
                "- Follow rework or rejection instructions if operations sends them back.",
            )),
            ("Status and environment modes", (
                "If the platform is in maintenance or read-only mode, mobile shows the status and blocks risky submissions until operations reopens write access.",
            )),
        ),
        checklist=(
            "Keep the app updated and location permissions enabled.",
            "Confirm site details before submitting proof.",
            "Do not expose finance or admin screenshots to field-only users.",
            "Contact operations if upload retry repeatedly fails.",
        ),
    ),
)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for guide in GUIDES:
        build(guide)
        print(f"Generated {guide.filename}")


if __name__ == "__main__":
    main()
