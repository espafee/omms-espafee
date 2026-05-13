from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from core.roles import ADMIN, FIELD_STAFF, FINANCE, OPERATIONS


@dataclass(frozen=True)
class TrainingDocument:
    slug: str
    title: str
    audience: str
    filename: str
    allowed_roles: tuple[str, ...] = ()

    @property
    def path(self) -> Path:
        return settings.BASE_DIR / "docs" / "training" / self.filename


ADMIN_ROLES = (ADMIN,)

TRAINING_DOCUMENTS: dict[str, TrainingDocument] = {
    "master-manual": TrainingDocument(
        slug="master-manual",
        title="OMMS Master Training Manual",
        audience="All OMMS users",
        filename="OMMS_Master_Training_Manual.pdf",
    ),
    "field-staff": TrainingDocument(
        slug="field-staff",
        title="Field Staff Training Guide",
        audience="Field staff and execution teams",
        filename="OMMS_Field_Staff_Training_Guide.pdf",
        allowed_roles=(ADMIN, OPERATIONS, FIELD_STAFF),
    ),
    "finance-team": TrainingDocument(
        slug="finance-team",
        title="Finance Team Guide",
        audience="Finance and accounts teams",
        filename="OMMS_Finance_Team_Guide.pdf",
        allowed_roles=(ADMIN, FINANCE),
    ),
    "operations-team": TrainingDocument(
        slug="operations-team",
        title="Operations Team Guide",
        audience="Operations managers",
        filename="OMMS_Operations_Team_Guide.pdf",
        allowed_roles=(ADMIN, OPERATIONS),
    ),
    "inventory-management": TrainingDocument(
        slug="inventory-management",
        title="Inventory Management Guide",
        audience="Inventory managers",
        filename="OMMS_Inventory_Management_Guide.pdf",
        allowed_roles=(ADMIN, OPERATIONS),
    ),
    "admin-super-admin": TrainingDocument(
        slug="admin-super-admin",
        title="Admin and Super Admin Guide",
        audience="Admins and owners",
        filename="OMMS_Admin_Super_Admin_Guide.pdf",
        allowed_roles=(ADMIN,),
    ),
}


def user_can_view_document(user, document: TrainingDocument) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "role", None) in ADMIN_ROLES:
        return True
    if not document.allowed_roles:
        return True
    return getattr(user, "role", None) in document.allowed_roles


def visible_documents_for_user(user) -> list[TrainingDocument]:
    return [document for document in TRAINING_DOCUMENTS.values() if user_can_view_document(user, document)]
