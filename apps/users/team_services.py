from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.bookings.models import Assignment
from apps.observability.services import record_audit_event
from apps.tenants.models import Tenant
from apps.tenants.services import get_user_tenant, is_company_admin, is_platform_super_admin
from core.roles import TEAM_ASSIGNABLE_ROLES

User = get_user_model()


TEAM_ROLE_DEFINITIONS = (
    {
        "key": "company_admin",
        "value": User.Role.ADMIN,
        "label": "Company Admin",
        "description": "Manage the company workspace, team, and operational settings.",
        "capabilities": ["team", "campaigns", "inventory", "poe", "billing", "operations"],
    },
    {
        "key": "operations_manager",
        "value": User.Role.OPERATIONS,
        "label": "Operations Manager",
        "description": "Coordinate inventory, POE operations, alerts, and execution workflows.",
        "capabilities": ["campaigns", "inventory", "poe", "operations"],
    },
    {
        "key": "field_staff",
        "value": User.Role.FIELD_STAFF,
        "label": "Field Staff",
        "description": "View assigned work and submit field proof of execution.",
        "capabilities": ["assigned_work", "poe_upload", "mobile"],
    },
    {
        "key": "poe_reviewer",
        "value": User.Role.POE_REVIEWER,
        "label": "POE Reviewer",
        "description": "Review, approve, or reject tenant POE records.",
        "capabilities": ["campaign_read", "booking_read", "poe_review"],
    },
    {
        "key": "finance",
        "value": User.Role.FINANCE,
        "label": "Finance",
        "description": "Manage invoices, payments, statements, and collection workflows.",
        "capabilities": ["billing", "payments", "finance_analytics"],
    },
    {
        "key": "inventory_manager",
        "value": User.Role.INVENTORY_MANAGER,
        "label": "Inventory Manager",
        "description": "Maintain sites, media units, rates, and inventory media.",
        "capabilities": ["inventory"],
    },
    {
        "key": "client_viewer",
        "value": User.Role.CLIENT,
        "label": "Client Viewer",
        "description": "View only client-safe campaigns, approved POE, and permitted billing records.",
        "capabilities": ["client_campaigns", "approved_poe", "client_billing"],
    },
)


def can_manage_team(user) -> bool:
    return is_platform_super_admin(user) or is_company_admin(user)


def team_user_queryset(actor):
    queryset = (
        User.objects.select_related("tenant", "reports_to")
        .filter(tenant__tenant_type=Tenant.TenantType.CLIENT)
        .annotate(
            assigned_work_count=Count(
                "booking_assignments",
                filter=Q(booking_assignments__status=Assignment.Status.PENDING),
                distinct=True,
            ),
            managed_campaign_count=Count("managed_campaigns", distinct=True),
        )
    )
    if is_platform_super_admin(actor):
        return queryset.order_by("-created_at", "-id")
    tenant = get_user_tenant(actor)
    if tenant is None:
        return queryset.none()
    return queryset.filter(tenant=tenant).order_by("-created_at", "-id")


def available_team_tenants(actor):
    if not is_platform_super_admin(actor):
        return Tenant.objects.filter(pk=getattr(actor, "tenant_id", None))
    return Tenant.objects.filter(tenant_type=Tenant.TenantType.CLIENT).order_by("name", "id")


def _record_team_event(*, actor, target, event_type, summary, severity="info", metadata=None):
    return record_audit_event(
        event_type=event_type,
        entity_type="user",
        entity_id=getattr(target, "id", ""),
        actor=actor,
        severity=severity,
        summary=summary,
        metadata={
            "target_tenant_id": getattr(target, "tenant_id", None),
            "target_role": getattr(target, "role", ""),
            **(metadata or {}),
        },
    )


def record_prohibited_team_action(*, actor, target_id=None, reason="prohibited_operation"):
    record_audit_event(
        event_type="team.access.denied",
        entity_type="user",
        entity_id=target_id or "",
        actor=actor,
        severity="warning",
        summary="A prohibited team-management operation was blocked.",
        metadata={"reason": reason, "actor_tenant_id": getattr(actor, "tenant_id", None)},
    )


def _resolve_create_tenant(actor, requested_tenant):
    if is_platform_super_admin(actor):
        if requested_tenant is None:
            raise ValidationError({"tenant": ["Select the company this team member belongs to."]})
        if requested_tenant.tenant_type != Tenant.TenantType.CLIENT:
            record_prohibited_team_action(actor=actor, reason="platform_tenant_assignment")
            raise ValidationError({"tenant": ["Team members can only be created inside a client company."]})
        return requested_tenant

    actor_tenant = get_user_tenant(actor)
    if requested_tenant is not None and requested_tenant != actor_tenant:
        record_prohibited_team_action(actor=actor, reason="cross_tenant_create")
        raise ValidationError({"tenant": ["You can only create team members inside your own company."]})
    return actor_tenant


def _build_username(email):
    base = slugify(email.split("@", 1)[0]).replace("-", "_")[:120] or "team_member"
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base[:140 - len(str(suffix))]}_{suffix}"
    return candidate


def _validate_role(actor, role):
    if role not in TEAM_ASSIGNABLE_ROLES:
        record_prohibited_team_action(actor=actor, reason="unsupported_role")
        raise ValidationError({"role": ["Select one of the supported company roles."]})


def _validate_manager(tenant, reports_to):
    if reports_to is not None and reports_to.tenant_id != getattr(tenant, "id", None):
        raise ValidationError({"reports_to": ["The reporting manager must belong to the same company."]})


@transaction.atomic
def create_team_user(*, actor, email, first_name="", last_name="", phone_number="", role, region="", reports_to=None, tenant=None):
    if not can_manage_team(actor):
        raise PermissionDenied("You do not have permission to manage company users.")
    _validate_role(actor, role)
    tenant = _resolve_create_tenant(actor, tenant)
    _validate_manager(tenant, reports_to)
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": ["A user with this email already exists."]})

    user = User.objects.create_user(
        email=email.lower(),
        username=_build_username(email),
        password=None,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        role=role,
        region=region,
        reports_to=reports_to,
        tenant=tenant,
        is_active=True,
    )
    _record_team_event(
        actor=actor,
        target=user,
        event_type="team.user.created",
        summary="A company team member was created.",
    )
    return user


@transaction.atomic
def update_team_user(*, actor, target, **changes):
    if target.is_superuser or target.tenant.tenant_type != Tenant.TenantType.CLIENT:
        record_prohibited_team_action(actor=actor, target_id=target.id, reason="platform_user_edit")
        raise PermissionDenied("Platform administrator accounts cannot be changed from company team management.")
    if "tenant" in changes and changes["tenant"] != target.tenant:
        record_prohibited_team_action(actor=actor, target_id=target.id, reason="tenant_move")
        raise ValidationError({"tenant": ["Moving an existing user between companies is not supported."]})
    if "role" in changes:
        _validate_role(actor, changes["role"])
    _validate_manager(target.tenant, changes.get("reports_to", target.reports_to))

    old_role = target.role
    for field in ("first_name", "last_name", "phone_number", "role", "region", "reports_to"):
        if field in changes:
            setattr(target, field, changes[field])
    target.save()
    if target.role != old_role:
        _record_team_event(
            actor=actor,
            target=target,
            event_type="team.user.role_changed",
            summary="A company team member role was changed.",
            metadata={"previous_role": old_role, "new_role": target.role},
        )
    return target


@transaction.atomic
def set_team_user_active(*, actor, target, is_active):
    if target.id == actor.id:
        raise ValidationError({"detail": ["You cannot remove your own access."]})
    if target.is_superuser:
        record_prohibited_team_action(actor=actor, target_id=target.id, reason="platform_user_access_change")
        raise PermissionDenied("Platform administrator access cannot be changed here.")
    target.is_active = is_active
    target.save(update_fields=["is_active", "updated_at"])
    _record_team_event(
        actor=actor,
        target=target,
        event_type="team.user.access_restored" if is_active else "team.user.access_removed",
        summary="A company team member's access was restored." if is_active else "A company team member's access was removed.",
        severity="info" if is_active else "warning",
    )
    return target


def build_password_setup_url(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    base_url = settings.FRONTEND_PUBLIC_BASE_URL.rstrip("/")
    return f"{base_url}/account-setup?uid={uid}&token={token}"


def send_team_setup_email(*, actor, target):
    if not target.is_active:
        raise ValidationError({"detail": ["Restore this user's access before sending account setup."]})
    setup_url = build_password_setup_url(target)
    company_name = target.tenant.name if target.tenant_id else "OMMS"
    message = EmailMessage(
        subject=f"Set up your {company_name} OMMS account",
        body=(
            f"Hello {target.get_full_name() or target.email},\n\n"
            f"Your OMMS account is ready. Use the secure link below to set your password:\n\n{setup_url}\n\n"
            "If you were not expecting this invitation, contact your company administrator."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[target.email],
    )
    message.send(fail_silently=False)
    target.setup_sent_at = timezone.now()
    target.save(update_fields=["setup_sent_at", "updated_at"])
    _record_team_event(
        actor=actor,
        target=target,
        event_type="team.user.setup_sent",
        summary="Account setup instructions were sent to a company team member.",
    )
    return target
