from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Count, QuerySet
from django.db.models.functions import Lower

from apps.billing.models import CampaignEstimate, Invoice, InvoiceSequence, SupplierProfile
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.notifications.models import EmailNotificationLog, Notification, NotificationPreference
from apps.observability.models import AlertEvent, AlertRule, DashboardWidgetPreference, ImportExportJob, SavedOperationalView
from apps.poe.models import ProofOfExecution


@dataclass(frozen=True)
class IdentifierTarget:
    key: str
    label: str
    model_label: str
    field: str
    tenant_path: str
    current_constraint: str
    target_constraint: str
    phase_1g_action: str
    blank_is_ignored: bool = True


IDENTIFIER_TARGETS: tuple[IdentifierTarget, ...] = (
    IdentifierTarget(
        key="media_site_code",
        label="Media site code",
        model_label="inventory.MediaSite",
        field="code",
        tenant_path="tenant",
        current_constraint="global unique field: MediaSite.code",
        target_constraint="unique per tenant: tenant + normalized code",
        phase_1g_action="Audit duplicate/case-colliding site codes, then replace global unique code with a tenant-scoped constraint.",
    ),
    IdentifierTarget(
        key="media_unit_code",
        label="Media unit code",
        model_label="inventory.MediaUnit",
        field="unit_code",
        tenant_path="site__tenant",
        current_constraint="global unique field: MediaUnit.unit_code",
        target_constraint="unique per tenant: tenant + normalized unit_code",
        phase_1g_action="Add direct tenant ownership or a DB-supported scoped design before relaxing global unit-code uniqueness.",
    ),
    IdentifierTarget(
        key="campaign_code",
        label="Campaign code",
        model_label="campaigns.Campaign",
        field="code",
        tenant_path="tenant",
        current_constraint="global unique field: Campaign.code",
        target_constraint="unique per tenant: tenant + normalized code",
        phase_1g_action="Audit duplicate/case-colliding campaign codes, then introduce tenant-scoped campaign-code uniqueness.",
    ),
    IdentifierTarget(
        key="invoice_number",
        label="Invoice number",
        model_label="billing.Invoice",
        field="invoice_number",
        tenant_path="campaign__tenant",
        current_constraint="global unique nullable field: Invoice.invoice_number",
        target_constraint="unique per tenant for issued invoice numbers",
        phase_1g_action="Introduce tenant-owned invoice sequences before changing invoice-number uniqueness.",
    ),
    IdentifierTarget(
        key="estimate_number",
        label="Estimate number",
        model_label="billing.CampaignEstimate",
        field="estimate_number",
        tenant_path="client__tenant",
        current_constraint="global unique nullable field: CampaignEstimate.estimate_number",
        target_constraint="unique per tenant for non-empty estimate numbers",
        phase_1g_action="Introduce tenant-owned estimate numbering or tenant FK on estimates before changing uniqueness.",
    ),
    IdentifierTarget(
        key="poe_client_upload_id",
        label="POE client upload id",
        model_label="poe.ProofOfExecution",
        field="client_upload_id",
        tenant_path="booking__campaign__tenant",
        current_constraint="global non-empty unique constraint: unique_non_empty_poe_client_upload_id",
        target_constraint="unique per tenant for non-empty client_upload_id",
        phase_1g_action="Add direct POE tenant ownership or a safe tenant-scoped idempotency key before relaxing the global constraint.",
    ),
    IdentifierTarget(
        key="supplier_gstin",
        label="Supplier GSTIN",
        model_label="billing.SupplierProfile",
        field="gstin",
        tenant_path="tenant",
        current_constraint="global unique field: SupplierProfile.gstin",
        target_constraint="business decision pending: global legal identity or tenant-scoped supplier profile",
        phase_1g_action="Confirm legal/business rule before changing GSTIN uniqueness.",
    ),
    IdentifierTarget(
        key="alert_rule_metric",
        label="Alert rule metric",
        model_label="observability.AlertRule",
        field="metric",
        tenant_path="tenant",
        current_constraint="global unique field: AlertRule.metric",
        target_constraint="one platform default per metric plus optional tenant override per tenant + metric",
        phase_1g_action="Design platform-default versus tenant-override alert rules before changing metric uniqueness.",
    ),
    IdentifierTarget(
        key="saved_operational_view_name",
        label="Saved view name",
        model_label="observability.SavedOperationalView",
        field="name",
        tenant_path="tenant",
        current_constraint="legacy unique_together: user + company_name + name",
        target_constraint="unique per user + tenant + name",
        phase_1g_action="Migrate legacy company_name uniqueness to user + tenant + name after tenant backfill is proven.",
    ),
    IdentifierTarget(
        key="dashboard_widget_preference_key",
        label="Dashboard widget preference key",
        model_label="observability.DashboardWidgetPreference",
        field="widget_key",
        tenant_path="tenant",
        current_constraint="legacy unique_together: user + company_name + widget_key",
        target_constraint="unique per user + tenant + widget_key",
        phase_1g_action="Migrate legacy company_name uniqueness to user + tenant + widget_key after tenant backfill is proven.",
    ),
)


MODEL_MAP = {
    "inventory.MediaSite": MediaSite,
    "inventory.MediaUnit": MediaUnit,
    "campaigns.Campaign": Campaign,
    "billing.Invoice": Invoice,
    "billing.CampaignEstimate": CampaignEstimate,
    "billing.SupplierProfile": SupplierProfile,
    "poe.ProofOfExecution": ProofOfExecution,
    "observability.AlertRule": AlertRule,
    "observability.SavedOperationalView": SavedOperationalView,
    "observability.DashboardWidgetPreference": DashboardWidgetPreference,
}


SEQUENCE_OWNERSHIP_GAPS = [
    {
        "key": "invoice_sequence",
        "model": "billing.InvoiceSequence",
        "current_owner": "global",
        "current_constraint": "unique_together(document_type, financial_year)",
        "risk": "All tenants currently share the same invoice sequence bucket.",
        "phase_1g_action": "Add tenant ownership to InvoiceSequence and migrate uniqueness to tenant + document_type + financial_year.",
    },
    {
        "key": "invoice_number_generation",
        "model": "billing.Invoice",
        "current_owner": "global sequence generated by allocate_invoice_number(document_type, financial_year)",
        "current_constraint": "Invoice.invoice_number is globally unique",
        "risk": "Tenant-specific invoice numbering cannot safely start until sequence ownership is tenant-aware.",
        "phase_1g_action": "Pass tenant into invoice allocation and preserve existing issued numbers as immutable historical identifiers.",
    },
    {
        "key": "estimate_number_generation",
        "model": "billing.CampaignEstimate",
        "current_owner": "global primary-key based number generated as EST/{created_at:%Y-%y}/{id:04d}",
        "current_constraint": "CampaignEstimate.estimate_number is globally unique",
        "risk": "Estimate numbers are not owned by tenant or a financial-year sequence.",
        "phase_1g_action": "Add tenant ownership and a tenant-owned estimate sequence before changing uniqueness.",
    },
    {
        "key": "poe_client_upload_id_idempotency",
        "model": "poe.ProofOfExecution",
        "current_owner": "global DB uniqueness, service lookup narrows retry lookup to booking campaign tenant",
        "current_constraint": "unique_non_empty_poe_client_upload_id",
        "risk": "Service behavior is tenant-aware, but DB uniqueness still blocks two tenants using the same mobile upload id.",
        "phase_1g_action": "Move idempotency uniqueness to tenant + non-empty client_upload_id after POE tenant ownership is explicit.",
    },
    {
        "key": "import_export_file_names",
        "model": "observability.ImportExportJob",
        "current_owner": "job-owned files under imports/ and exports/",
        "current_constraint": "no DB uniqueness; filenames include uploaded filename or job-specific report names in some paths",
        "risk": "Storage keys may be readable but should become tenant/job namespaced for long-term SaaS hygiene.",
        "phase_1g_action": "Prefer tenant slug + job id in generated report/export paths while preserving existing downloads.",
    },
]


NULL_TENANT_CHECKS = [
    ("inventory.MediaSite", MediaSite.objects.all(), "tenant"),
    ("campaigns.Campaign", Campaign.objects.all(), "tenant"),
    ("billing.SupplierProfile", SupplierProfile.objects.all(), "tenant"),
    ("billing.Invoice", Invoice.objects.all(), "campaign__tenant"),
    ("billing.CampaignEstimate.client", CampaignEstimate.objects.all(), "client__tenant"),
    ("billing.CampaignEstimate.campaign", CampaignEstimate.objects.exclude(campaign__isnull=True), "campaign__tenant"),
    ("poe.ProofOfExecution", ProofOfExecution.objects.all(), "booking__campaign__tenant"),
    ("observability.ImportExportJob", ImportExportJob.objects.all(), "tenant"),
    ("notifications.Notification", Notification.objects.all(), "tenant"),
    ("notifications.EmailNotificationLog", EmailNotificationLog.objects.all(), "tenant"),
    ("notifications.NotificationPreference.user", NotificationPreference.objects.all(), "user__tenant"),
    ("observability.AlertRule", AlertRule.objects.all(), "tenant"),
    ("observability.AlertEvent", AlertEvent.objects.all(), "tenant"),
    ("observability.SavedOperationalView", SavedOperationalView.objects.all(), "tenant"),
    ("observability.DashboardWidgetPreference", DashboardWidgetPreference.objects.all(), "tenant"),
]


def _identifier_queryset_for(target: IdentifierTarget) -> QuerySet:
    queryset = MODEL_MAP[target.model_label].objects.all()
    if target.blank_is_ignored:
        queryset = queryset.exclude(**{f"{target.field}__isnull": True}).exclude(**{target.field: ""})
    return queryset


def _duplicate_groups_for(target: IdentifierTarget) -> list[dict[str, Any]]:
    queryset = (
        _identifier_queryset_for(target)
        .annotate(normalized_identifier=Lower(target.field))
        .values("normalized_identifier")
        .annotate(row_count=Count("id"), tenant_count=Count(target.tenant_path, distinct=True))
        .filter(row_count__gt=1)
        .order_by("-row_count", "normalized_identifier")[:25]
    )
    return [
        {
            "identifier": row["normalized_identifier"],
            "row_count": row["row_count"],
            "tenant_count": row["tenant_count"],
            "risk": "cross-tenant" if row["tenant_count"] > 1 else "same-tenant-or-case-collision",
        }
        for row in queryset
    ]


def _null_tenant_count(queryset: QuerySet, tenant_path: str) -> int:
    return queryset.filter(**{f"{tenant_path}__isnull": True}).count()


def build_tenant_identifier_audit() -> dict[str, Any]:
    """Build a read-only tenant identifier/sequence audit for Phase 1F."""

    targets = []
    for target in IDENTIFIER_TARGETS:
        queryset = _identifier_queryset_for(target)
        targets.append(
            {
                "key": target.key,
                "label": target.label,
                "model": target.model_label,
                "field": target.field,
                "tenant_path": target.tenant_path,
                "record_count": queryset.count(),
                "null_tenant_count": _null_tenant_count(queryset, target.tenant_path),
                "current_constraint": target.current_constraint,
                "target_constraint": target.target_constraint,
                "duplicate_groups": _duplicate_groups_for(target),
                "phase_1g_action": target.phase_1g_action,
            }
        )

    null_tenant_records = [
        {
            "model": model_label,
            "tenant_path": tenant_path,
            "null_tenant_count": _null_tenant_count(queryset, tenant_path),
        }
        for model_label, queryset, tenant_path in NULL_TENANT_CHECKS
    ]

    global_uniqueness_blockers = [
        {
            "key": target.key,
            "model": target.model_label,
            "field": target.field,
            "current_constraint": target.current_constraint,
            "target_constraint": target.target_constraint,
            "phase_1g_action": target.phase_1g_action,
        }
        for target in IDENTIFIER_TARGETS
    ]

    return {
        "phase": "1F",
        "scope": "tenant-scoped identifier and sequence audit",
        "constraints_changed": False,
        "numbering_behavior_changed": False,
        "global_uniqueness_blockers": global_uniqueness_blockers,
        "identifier_targets": targets,
        "duplicate_risk_summary": {
            "targets_with_duplicate_groups": sum(1 for target in targets if target["duplicate_groups"]),
            "duplicate_groups_total": sum(len(target["duplicate_groups"]) for target in targets),
            "note": "Current global unique constraints may prevent real cross-tenant duplicate rows today; this audit also detects normalized case-collision risk.",
        },
        "null_tenant_records": null_tenant_records,
        "sequence_ownership_gaps": SEQUENCE_OWNERSHIP_GAPS,
        "phase_1g_recommendation": [
            "Run this audit in production and resolve any null-tenant or duplicate/case-collision findings before constraint changes.",
            "Introduce tenant-owned sequence context before changing billing invoice or estimate numbers.",
            "Migrate identifier constraints in small app-specific migrations, starting with inventory/campaign roots and then derived operational identifiers.",
            "Keep token/security uniqueness global; only business natural identifiers should move to tenant scope.",
        ],
    }
