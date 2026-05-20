from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Tenant


PLATFORM_TENANT_SLUG = "omms-platform"
DEFAULT_CLIENT_TENANT_SLUG = "vistaai-omms-beta"


def get_default_client_tenant() -> Tenant | None:
    return Tenant.objects.filter(is_default=True, tenant_type=Tenant.TenantType.CLIENT).first()


def get_platform_tenant() -> Tenant | None:
    return Tenant.objects.filter(slug=PLATFORM_TENANT_SLUG, tenant_type=Tenant.TenantType.PLATFORM).first()


def is_platform_super_admin(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    tenant = getattr(user, "tenant", None)
    return bool(
        getattr(user, "is_superuser", False)
        and tenant
        and tenant.tenant_type == Tenant.TenantType.PLATFORM
    )


def is_company_admin(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    tenant = getattr(user, "tenant", None)
    return bool(
        getattr(user, "role", "") == "admin"
        and tenant
        and tenant.tenant_type == Tenant.TenantType.CLIENT
    )


def get_user_tenant(user) -> Tenant | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "tenant", None)


def resolve_write_tenant(user, requested_tenant: Tenant | None = None) -> Tenant | None:
    if is_platform_super_admin(user):
        return requested_tenant or get_default_client_tenant() or get_user_tenant(user)

    user_tenant = get_user_tenant(user)
    if requested_tenant is not None and requested_tenant != user_tenant:
        raise ValidationError({"tenant": ["You can only create records inside your own company."]})
    return user_tenant


def require_same_tenant(user, tenant: Tenant | None, *, message: str = "You do not have access to this company data.") -> None:
    if is_platform_super_admin(user):
        return
    if tenant is None or tenant != get_user_tenant(user):
        raise PermissionDenied(message)


def scope_queryset_to_tenant_path(queryset: QuerySet, user, tenant_path: str = "tenant") -> QuerySet:
    if user is None:
        return queryset
    if is_platform_super_admin(user):
        return queryset

    tenant = get_user_tenant(user)
    if tenant is None:
        return queryset.none()
    return queryset.filter(**{tenant_path: tenant})


def scope_users_to_requesting_tenant(queryset: QuerySet, user) -> QuerySet:
    if is_platform_super_admin(user):
        return queryset

    tenant = get_user_tenant(user)
    if tenant is None:
        return queryset.none()
    return queryset.filter(tenant=tenant)


def assign_user_to_default_tenant(user) -> None:
    if getattr(user, "tenant_id", None):
        return

    tenant = get_platform_tenant() if getattr(user, "is_superuser", False) else get_default_client_tenant()
    if tenant is None:
        return
    User = get_user_model()
    User.objects.filter(pk=user.pk, tenant__isnull=True).update(tenant=tenant)
