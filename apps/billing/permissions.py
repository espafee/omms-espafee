from rest_framework.exceptions import PermissionDenied

from core.roles import ADMIN, CLIENT, FINANCE, SALES


FINANCE_PERMISSION_ROLES = {
    "view_invoice": {ADMIN, FINANCE, SALES, CLIENT},
    "issue_invoice": {ADMIN, FINANCE},
    "record_payment": {ADMIN, FINANCE},
    "void_invoice": {ADMIN, FINANCE},
    "export_statement": {ADMIN, FINANCE},
    "view_finance_dashboard": {ADMIN, FINANCE, SALES, CLIENT},
}


def has_finance_permission(user, permission: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "role", None) in FINANCE_PERMISSION_ROLES.get(permission, set())


def enforce_finance_permission(user, permission: str) -> None:
    if not has_finance_permission(user, permission):
        raise PermissionDenied("You do not have finance permission for this action.")
