from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantOwnershipPlan:
    app_label: str
    model: str
    ownership_path: str
    phase_1c_action: str
    uniqueness_changes: tuple[str, ...] = ()
    exposed_surfaces: tuple[str, ...] = ()
    notes: str = ""


TENANT_OWNERSHIP_AUDIT: tuple[TenantOwnershipPlan, ...] = (
    TenantOwnershipPlan(
        app_label="inventory",
        model="MediaSite",
        ownership_path="tenant",
        phase_1c_action="add nullable tenant FK, backfill default beta tenant, then scope repository/query filters",
        uniqueness_changes=("code: global unique -> unique per tenant",),
        exposed_surfaces=("inventory site API", "import preview", "inventory export", "operational search", "mobile admin search"),
    ),
    TenantOwnershipPlan(
        app_label="inventory",
        model="MediaUnit",
        ownership_path="site.tenant",
        phase_1c_action="derive tenant through site and enforce same-tenant writes",
        uniqueness_changes=("unit_code: global unique -> unique per tenant",),
        exposed_surfaces=("inventory unit API", "bookings", "import processing", "exports", "mobile assigned work"),
    ),
    TenantOwnershipPlan(
        app_label="campaigns",
        model="Campaign",
        ownership_path="tenant or client.tenant",
        phase_1c_action="add tenant FK, backfill from client tenant, enforce client/account manager same tenant",
        uniqueness_changes=("code: global unique -> unique per tenant",),
        exposed_surfaces=("campaign API", "dashboard analytics", "operational search", "public token resolution"),
    ),
    TenantOwnershipPlan(
        app_label="campaigns",
        model="CampaignAsset",
        ownership_path="campaign.tenant",
        phase_1c_action="scope through campaign and validate asset writes through campaign access",
        exposed_surfaces=("campaign asset API", "public campaign view"),
    ),
    TenantOwnershipPlan(
        app_label="bookings",
        model="Booking",
        ownership_path="campaign.tenant",
        phase_1c_action="scope through campaign and enforce campaign/media unit tenant match",
        uniqueness_changes=("campaign + media_unit + start_date + end_date remains tenant-derived",),
        exposed_surfaces=("booking API", "POE", "issues", "mobile assigned work"),
    ),
    TenantOwnershipPlan(
        app_label="bookings",
        model="Assignment",
        ownership_path="booking.campaign.tenant",
        phase_1c_action="scope through booking and enforce assigned user tenant match",
        uniqueness_changes=("booking + user remains tenant-derived",),
        exposed_surfaces=("mobile assigned work", "issues", "reviewer workload"),
    ),
    TenantOwnershipPlan(
        app_label="poe",
        model="ProofOfExecution",
        ownership_path="booking.campaign.tenant",
        phase_1c_action="scope through booking and preserve client-upload idempotency per tenant",
        uniqueness_changes=("client_upload_id: global non-empty unique -> unique per tenant when non-empty",),
        exposed_surfaces=("POE API", "POE review", "SLA analytics", "heatmap", "mobile upload"),
    ),
    TenantOwnershipPlan(
        app_label="poe",
        model="ProofOfExecutionMedia",
        ownership_path="poe_record.booking.campaign.tenant",
        phase_1c_action="scope through POE record and validate media upload access",
        exposed_surfaces=("POE media API", "training/screenshots references", "mobile upload"),
    ),
    TenantOwnershipPlan(
        app_label="billing",
        model="SupplierProfile",
        ownership_path="tenant",
        phase_1c_action="add tenant FK and scope finance APIs",
        uniqueness_changes=("gstin: evaluate legal uniqueness; likely unique per tenant or nullable duplicate-safe rule",),
        exposed_surfaces=("supplier API", "invoice generation", "PDF rendering"),
    ),
    TenantOwnershipPlan(
        app_label="billing",
        model="InvoiceSequence",
        ownership_path="tenant",
        phase_1c_action="add tenant FK before multi-tenant invoice generation",
        uniqueness_changes=("document_type + financial_year -> tenant + document_type + financial_year",),
        exposed_surfaces=("invoice number generation",),
    ),
    TenantOwnershipPlan(
        app_label="billing",
        model="Invoice",
        ownership_path="campaign.tenant",
        phase_1c_action="add tenant FK or derive from campaign; enforce finance role and tenant access",
        uniqueness_changes=("invoice_number: global unique -> unique per tenant",),
        exposed_surfaces=("billing API", "client statements", "exports", "dashboard billing intelligence"),
    ),
    TenantOwnershipPlan(
        app_label="billing",
        model="CampaignEstimate",
        ownership_path="client.tenant",
        phase_1c_action="add tenant FK, backfill from client, and scope estimate APIs",
        uniqueness_changes=("estimate_number: global unique -> unique per tenant",),
        exposed_surfaces=("estimate API", "public estimate token resolution", "billing dashboard"),
    ),
    TenantOwnershipPlan(
        app_label="issues",
        model="Issue",
        ownership_path="booking.campaign.tenant",
        phase_1c_action="scope through booking and enforce reporter/task assignee same tenant",
        exposed_surfaces=("issue API", "mobile admin issues", "alerts/escalations"),
    ),
    TenantOwnershipPlan(
        app_label="notifications",
        model="Notification",
        ownership_path="tenant or recipient.tenant",
        phase_1c_action="replace company_name-only targeting with tenant FK plus recipient fallback",
        exposed_surfaces=("notification inbox", "mobile alerts", "dashboard KPIs"),
    ),
    TenantOwnershipPlan(
        app_label="observability",
        model="ImportExportJob",
        ownership_path="tenant",
        phase_1c_action="add tenant FK while retaining company_name as display snapshot",
        exposed_surfaces=("import/export workbench", "downloads", "retry workflow", "operations dashboard"),
    ),
    TenantOwnershipPlan(
        app_label="observability",
        model="AuditEvent",
        ownership_path="tenant",
        phase_1c_action="add tenant FK while retaining company_name as display snapshot",
        exposed_surfaces=("audit timeline", "operations activity", "search"),
    ),
    TenantOwnershipPlan(
        app_label="observability",
        model="ApiRequestLog",
        ownership_path="tenant when authenticated",
        phase_1c_action="add nullable tenant FK and keep anonymous/system logs tenantless",
        exposed_surfaces=("diagnostics", "request analytics"),
    ),
    TenantOwnershipPlan(
        app_label="observability",
        model="SavedOperationalView",
        ownership_path="tenant or user.tenant",
        phase_1c_action="add tenant FK; preserve user ownership",
        uniqueness_changes=("user + company_name + name -> user + tenant + name",),
        exposed_surfaces=("saved views",),
    ),
    TenantOwnershipPlan(
        app_label="observability",
        model="DashboardWidgetPreference",
        ownership_path="tenant or user.tenant",
        phase_1c_action="add tenant FK; preserve user ownership",
        uniqueness_changes=("user + company_name + widget_key -> user + tenant + widget_key",),
        exposed_surfaces=("dashboard customization",),
    ),
    TenantOwnershipPlan(
        app_label="observability",
        model="AlertRule",
        ownership_path="tenant or platform",
        phase_1c_action="decide platform-default vs tenant override rules before changing unique metric",
        uniqueness_changes=("metric: global unique -> tenant + metric for tenant overrides",),
        exposed_surfaces=("alert thresholds", "operations dashboard"),
    ),
)


def models_requiring_tenant_ownership() -> list[str]:
    return [f"{item.app_label}.{item.model}" for item in TENANT_OWNERSHIP_AUDIT]


def uniqueness_constraints_requiring_redesign() -> dict[str, tuple[str, ...]]:
    return {
        f"{item.app_label}.{item.model}": item.uniqueness_changes
        for item in TENANT_OWNERSHIP_AUDIT
        if item.uniqueness_changes
    }


def exposed_surfaces_requiring_scoping() -> dict[str, tuple[str, ...]]:
    return {
        f"{item.app_label}.{item.model}": item.exposed_surfaces
        for item in TENANT_OWNERSHIP_AUDIT
        if item.exposed_surfaces
    }
