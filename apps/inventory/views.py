from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, OPERATIONS
from core.viewsets import ServiceModelViewSet

from .serializers import (
    MediaSiteImageSerializer,
    MediaSiteSerializer,
    MediaUnitImageSerializer,
    MediaUnitSerializer,
    RateCardSerializer,
)
from .services import (
    MediaSiteImageService,
    MediaSiteService,
    MediaUnitImageService,
    MediaUnitService,
    RateCardService,
)


class MediaSiteViewSet(ServiceModelViewSet):
    serializer_class = MediaSiteSerializer
    permission_classes = [RoleBasedPermission]
    service_class = MediaSiteService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)
    write_roles_by_action = {
        "create": (ADMIN,),
        "destroy": (ADMIN,),
    }
    filterset_fields = ["site_type", "city", "state"]
    search_fields = ["name", "code", "address", "city", "state"]
    ordering_fields = ["name", "created_at"]


class MediaUnitViewSet(ServiceModelViewSet):
    serializer_class = MediaUnitSerializer
    permission_classes = [RoleBasedPermission]
    service_class = MediaUnitService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)
    filterset_fields = ["status", "site", "is_illuminated", "site_type", "facing_direction", "site__city"]
    search_fields = ["unit_code", "site__name", "site__code"]
    ordering_fields = ["unit_code", "monthly_rate", "created_at"]


class RateCardViewSet(ServiceModelViewSet):
    serializer_class = RateCardSerializer
    permission_classes = [RoleBasedPermission]
    service_class = RateCardService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)
    filterset_fields = ["unit", "start_date", "end_date"]
    ordering_fields = ["start_date", "end_date", "base_rate"]


class MediaSiteImageViewSet(ServiceModelViewSet):
    serializer_class = MediaSiteImageSerializer
    permission_classes = [RoleBasedPermission]
    service_class = MediaSiteImageService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["site", "is_primary"]
    search_fields = ["site__name", "site__code", "caption"]
    ordering_fields = ["uploaded_at", "created_at"]


class MediaUnitImageViewSet(ServiceModelViewSet):
    serializer_class = MediaUnitImageSerializer
    permission_classes = [RoleBasedPermission]
    service_class = MediaUnitImageService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["media_unit", "is_primary"]
    search_fields = ["media_unit__unit_code", "media_unit__site__name", "caption"]
    ordering_fields = ["uploaded_at", "created_at"]
