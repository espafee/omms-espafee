from django.db.models import Q
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, INVENTORY_MANAGER, OPERATIONS, POE_REVIEWER
from core.viewsets import ServiceModelViewSet

from .serializers import (
    InventorySiteListSerializer,
    InventoryUnitListSerializer,
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
    allowed_roles = ALL_ROLES + (INVENTORY_MANAGER, POE_REVIEWER)
    write_roles = (ADMIN, OPERATIONS, INVENTORY_MANAGER)
    write_roles_by_action = {
        "create": (ADMIN,),
        "destroy": (ADMIN,),
    }
    filterset_fields = ["site_type", "city", "state"]
    search_fields = ["name", "code", "address", "city", "state", "units__unit_code", "units__facing_direction"]
    ordering_fields = ["name", "code", "city", "created_at", "updated_at"]

    @action(detail=False, methods=["get"], url_path="all-sites")
    def all_sites(self, request):
        queryset = self.get_queryset().prefetch_related("images", "units", "units__images")
        city = request.query_params.get("city")
        status = request.query_params.get("status")
        media_type = request.query_params.get("media_type")
        facing_direction = request.query_params.get("facing_direction")
        unit_site_type = request.query_params.get("site_type")
        photo_status = request.query_params.get("photo_status")
        coordinate_status = request.query_params.get("coordinate_status")
        search = request.query_params.get("search")

        if city:
            queryset = queryset.filter(city=city)
        if status == "no_units":
            queryset = queryset.filter(units__isnull=True)
        elif status:
            queryset = queryset.filter(units__status=status)
        if media_type:
            queryset = queryset.filter(site_type=media_type)
        if facing_direction:
            queryset = queryset.filter(units__facing_direction__icontains=facing_direction)
        if unit_site_type:
            queryset = queryset.filter(units__site_type=unit_site_type)
        if photo_status == "with_photos":
            queryset = queryset.filter(images__isnull=False)
        elif photo_status == "missing_photos":
            queryset = queryset.filter(images__isnull=True)
        if coordinate_status == "coordinates_set":
            queryset = queryset.filter(latitude__isnull=False, longitude__isnull=False)
        elif coordinate_status == "coordinates_missing":
            queryset = queryset.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(address__icontains=search)
                | Q(city__icontains=search)
                | Q(state__icontains=search)
                | Q(units__unit_code__icontains=search)
                | Q(units__facing_direction__icontains=search)
            )

        ordering = request.query_params.get("ordering")
        ordering_map = {
            "title": "name",
            "-title": "-name",
            "site_code": "code",
            "-site_code": "-code",
            "city": "city",
            "-city": "-city",
            "created_at": "created_at",
            "-created_at": "-created_at",
            "updated_at": "updated_at",
            "-updated_at": "-updated_at",
        }
        if ordering in ordering_map:
            queryset = queryset.order_by(ordering_map[ordering])

        queryset = queryset.distinct()
        page = self.paginate_queryset(queryset)
        serializer_context = self.get_serializer_context()
        if page is not None:
            serializer = InventorySiteListSerializer(page, many=True, context=serializer_context)
            return self.get_paginated_response(serializer.data)

        serializer = InventorySiteListSerializer(queryset, many=True, context=serializer_context)
        return Response(serializer.data)


class MediaUnitViewSet(ServiceModelViewSet):
    serializer_class = MediaUnitSerializer
    permission_classes = [RoleBasedPermission]
    service_class = MediaUnitService
    allowed_roles = ALL_ROLES + (INVENTORY_MANAGER, POE_REVIEWER)
    write_roles = (ADMIN, OPERATIONS, INVENTORY_MANAGER)
    filterset_fields = ["status", "site", "is_illuminated", "site_type", "facing_direction", "site__city", "site__site_type"]
    search_fields = ["unit_code", "site__name", "site__code", "site__address", "site__city"]
    ordering_fields = ["unit_code", "monthly_rate", "status", "created_at", "updated_at", "site__city", "site__code"]

    @action(detail=False, methods=["post"], url_path="bulk-publication")
    def bulk_publication(self, request):
        unit_ids = request.data.get("unit_ids") or []
        if not isinstance(unit_ids, list) or not unit_ids:
            return Response({"unit_ids": ["Select at least one advertising unit."]}, status=status.HTTP_400_BAD_REQUEST)
        is_publicly_listed = request.data.get("is_publicly_listed")
        if not isinstance(is_publicly_listed, bool):
            return Response({"is_publicly_listed": ["Use true to publish or false to unpublish."]}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset().filter(id__in=unit_ids)
        updated_count = queryset.update(is_publicly_listed=is_publicly_listed)
        return Response({"updated_count": updated_count, "is_publicly_listed": is_publicly_listed})

    @action(detail=False, methods=["get"], url_path="all-units")
    def all_units(self, request):
        queryset = self.get_queryset().select_related("site").prefetch_related("images", "site__images")
        city = request.query_params.get("city")
        status = request.query_params.get("status")
        display_type = request.query_params.get("site_type")
        facing_direction = request.query_params.get("facing_direction")
        illuminated = request.query_params.get("is_illuminated")
        size = request.query_params.get("size")
        search = request.query_params.get("search")

        if city:
            queryset = queryset.filter(site__city=city)
        if status:
            queryset = queryset.filter(status=status)
        if display_type:
            queryset = queryset.filter(site_type=display_type)
        if facing_direction:
            queryset = queryset.filter(facing_direction__icontains=facing_direction)
        if illuminated in {"true", "false"}:
            queryset = queryset.filter(is_illuminated=illuminated == "true")
        if size and "x" in size:
            width, height = (part.strip() for part in size.split("x", 1))
            if width and height:
                queryset = queryset.filter(width=width, height=height)
        if search:
            queryset = queryset.filter(
                Q(unit_code__icontains=search)
                | Q(site__name__icontains=search)
                | Q(site__code__icontains=search)
                | Q(site__address__icontains=search)
                | Q(site__city__icontains=search)
                | Q(facing_direction__icontains=search)
            )

        ordering = request.query_params.get("ordering")
        ordering_map = {
            "unit_code": "unit_code",
            "-unit_code": "-unit_code",
            "monthly_rate": "monthly_rate",
            "-monthly_rate": "-monthly_rate",
            "status": "status",
            "-status": "-status",
            "city": "site__city",
            "-city": "-site__city",
            "updated_at": "updated_at",
            "-updated_at": "-updated_at",
        }
        queryset = queryset.order_by(ordering_map.get(ordering, "unit_code"))
        page = self.paginate_queryset(queryset)
        serializer_context = self.get_serializer_context()
        if page is not None:
            serializer = InventoryUnitListSerializer(page, many=True, context=serializer_context)
            return self.get_paginated_response(serializer.data)

        serializer = InventoryUnitListSerializer(queryset, many=True, context=serializer_context)
        return Response(serializer.data)


class RateCardViewSet(ServiceModelViewSet):
    serializer_class = RateCardSerializer
    permission_classes = [RoleBasedPermission]
    service_class = RateCardService
    allowed_roles = ALL_ROLES + (INVENTORY_MANAGER, POE_REVIEWER)
    write_roles = (ADMIN, OPERATIONS, INVENTORY_MANAGER)
    filterset_fields = ["unit", "start_date", "end_date"]
    ordering_fields = ["start_date", "end_date", "base_rate"]


class MediaSiteImageViewSet(ServiceModelViewSet):
    serializer_class = MediaSiteImageSerializer
    permission_classes = [RoleBasedPermission]
    service_class = MediaSiteImageService
    allowed_roles = ALL_ROLES + (INVENTORY_MANAGER, POE_REVIEWER)
    write_roles = (ADMIN, OPERATIONS, INVENTORY_MANAGER)
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["site", "is_primary"]
    search_fields = ["site__name", "site__code", "caption"]
    ordering_fields = ["uploaded_at", "created_at"]


class MediaUnitImageViewSet(ServiceModelViewSet):
    serializer_class = MediaUnitImageSerializer
    permission_classes = [RoleBasedPermission]
    service_class = MediaUnitImageService
    allowed_roles = ALL_ROLES + (INVENTORY_MANAGER, POE_REVIEWER)
    write_roles = (ADMIN, OPERATIONS, INVENTORY_MANAGER)
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["media_unit", "is_primary"]
    search_fields = ["media_unit__unit_code", "media_unit__site__name", "caption"]
    ordering_fields = ["uploaded_at", "created_at"]
