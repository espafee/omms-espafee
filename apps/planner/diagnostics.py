from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Q

from apps.inventory.models import MediaUnit

from .models import MediaPlannerShareLink
from .serializers import serialize_public_unit
from .services import (
    AvailabilityStatus,
    InventoryAvailabilityService,
    PlannerEligibilityEvaluator,
    _coerced_allowed_values,
    _filter_normalized_text,
    _normalized_allowed_values,
    planner_unit_queryset,
)


REQUIRED_MIGRATIONS = (
    ("inventory", "0009_mediaunit_is_publicly_listed_and_more"),
    ("planner", "0001_initial"),
)
SAMPLE_LIMIT = 25
DETAIL_LIMIT = 500


@dataclass(frozen=True)
class MediaPlannerDiagnosticsRequest:
    link: MediaPlannerShareLink
    unit_codes: tuple[str, ...] = ()
    start_date: Any = None
    end_date: Any = None


class MediaPlannerDiagnosticsService:
    """Read-only evidence for production media planner visibility debugging."""

    def build(self, request: MediaPlannerDiagnosticsRequest) -> dict[str, Any]:
        link = request.link
        start_date = request.start_date
        end_date = request.end_date
        unit_codes = request.unit_codes

        all_units = MediaUnit.objects.select_related("site")
        tenant_units = all_units.filter(site__tenant=link.tenant)
        public_units = tenant_units.filter(is_publicly_listed=True)
        active_units = public_units.exclude(status=MediaUnit.Status.RETIRED)
        operational_units = active_units
        parent_location_units = operational_units

        city_units = parent_location_units
        if link.allowed_cities:
            city_units = _filter_normalized_text(city_units, "site__city", link.allowed_cities, "_diagnostic_city")

        region_units = city_units
        if link.allowed_regions:
            region_units = _filter_normalized_text(region_units, "site__state", link.allowed_regions, "_diagnostic_region")

        type_units = region_units
        if link.allowed_inventory_types:
            inventory_types = _coerced_allowed_values(link.allowed_inventory_types)
            type_units = type_units.filter(Q(site_type__in=inventory_types) | Q(site__site_type__in=inventory_types))

        final_queryset = planner_unit_queryset(link, start_date=start_date, end_date=end_date)
        final_ids = set(final_queryset.values_list("id", flat=True))
        availability_service = InventoryAvailabilityService()
        final_units = list(final_queryset[:SAMPLE_LIMIT])
        serialization_error_count = 0
        for unit in final_units:
            try:
                serialize_public_unit(
                    unit,
                    link=link,
                    request=None,
                    availability=availability_service.resolve(unit, start_date=start_date, end_date=end_date),
                )
            except Exception:
                serialization_error_count += 1

        available_for_dates = self._available_for_requested_dates(type_units, start_date=start_date, end_date=end_date)
        sampled_units = self._sample_units(
            all_units=all_units,
            link=link,
            final_ids=final_ids,
            unit_codes=unit_codes,
            start_date=start_date,
            end_date=end_date,
        )
        exclusions = self._group_exclusions(
            all_units=all_units,
            link=link,
            final_ids=final_ids,
            start_date=start_date,
            end_date=end_date,
        )

        final_count = final_queryset.count()
        published_count = public_units.count()
        eligible_location_count = final_queryset.values("site_id").distinct().count()
        excluded_unit_rows = self._excluded_unit_rows(
            all_units=all_units,
            link=link,
            final_ids=final_ids,
            start_date=start_date,
            end_date=end_date,
        )
        excluded_count = all_units.exclude(id__in=final_ids).count()
        eligible_unit_rows = [
            self._unit_detail(unit, link=link, final_ids=final_ids, start_date=start_date, end_date=end_date)
            for unit in final_queryset[:DETAIL_LIMIT]
        ]
        excluded_location_count = len(
            {
                row["location_id"]
                for row in excluded_unit_rows
                if row.get("location_id") is not None
            }
        )
        summary = {
            "total_units_inspected": all_units.count(),
            "total_publicly_listed": all_units.filter(is_publicly_listed=True).count(),
            "total_eligible": final_count,
            "total_excluded": excluded_count,
            "unique_eligible_locations": eligible_location_count,
            "unique_excluded_locations": excluded_location_count,
            "eligible_detail_count": len(eligible_unit_rows),
            "excluded_detail_count": len(excluded_unit_rows),
            "detail_limit": DETAIL_LIMIT,
        }
        link_payload = {
            "id": link.id,
            "title": link.title,
            "tenant_id": link.tenant_id,
            "tenant_name": link.tenant.name,
            "active": link.is_available,
            "revoked": link.is_revoked,
            "expired": link.is_expired,
            "allowed_cities_type": type(link.allowed_cities).__name__ if link.allowed_cities is not None else "null",
            "allowed_cities": _coerced_allowed_values(link.allowed_cities),
            "pricing_mode": link.pricing_mode,
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
            "eligible_count": final_count,
            "published_count": published_count,
            "excluded_count": excluded_count,
            "unique_eligible_locations": eligible_location_count,
            "unique_excluded_locations": excluded_location_count,
        }
        pipeline = {
            "all_units": all_units.count(),
            "tenant_units": tenant_units.count(),
            "publicly_listed": published_count,
            "published_units": published_count,
            "active_units": active_units.count(),
            "operationally_eligible": operational_units.count(),
            "operational_units": operational_units.count(),
            "parent_location_eligible": parent_location_units.count(),
            "parent_active_units": parent_location_units.count(),
            "allowed_city_eligible": city_units.count(),
            "city_eligible_units": city_units.count(),
            "allowed_region_eligible": region_units.count(),
            "inventory_type_eligible": type_units.count(),
            "link_restriction_eligible": type_units.count(),
            "link_restriction_units": type_units.count(),
            "available_for_requested_dates": available_for_dates,
            "date_eligible": available_for_dates,
            "date_eligible_units": available_for_dates,
            "public_serializer_eligible": max(final_count - serialization_error_count, 0),
            "serializer_eligible_units": max(final_count - serialization_error_count, 0),
            "final_serialized": final_count,
            "final_units": final_count,
            "unique_eligible_locations": eligible_location_count,
            "unique_excluded_locations": excluded_location_count,
        }
        exclusions["parent_inactive"] = 0
        exclusions["date_unavailable"] = exclusions.get("unavailable_for_dates", 0)

        return {
            "service": self._service_identity(),
            "database": {
                "engine": self._database_engine_label(),
                "database_fingerprint": self._database_fingerprint(),
                "migration_status": self._migration_status(),
            },
            "link": link_payload,
            "summary": summary,
            "planner_link": {
                "id": link.id,
                "title": link.title,
                "tenant_id": link.tenant_id,
                "tenant_name": link.tenant.name,
                "is_active": link.is_available,
                "is_revoked": link.is_revoked,
                "is_expired": link.is_expired,
                "allowed_cities_raw_type": type(link.allowed_cities).__name__ if link.allowed_cities is not None else "null",
                "allowed_cities_safe_summary": _coerced_allowed_values(link.allowed_cities),
                "allowed_cities_normalized": _normalized_allowed_values(link.allowed_cities),
                "pricing_mode": link.pricing_mode,
                "expires_at": link.expires_at.isoformat() if link.expires_at else None,
                "eligible_count": final_count,
                "published_count": published_count,
                "excluded_count": excluded_count,
                "unique_eligible_locations": eligible_location_count,
                "unique_excluded_locations": excluded_location_count,
            },
            "pipeline": pipeline,
            "exclusions": exclusions,
            "sample_units": sampled_units,
            "units": sampled_units,
            "eligible_units": eligible_unit_rows,
            "excluded_units": excluded_unit_rows,
        }

    def _service_identity(self) -> dict[str, str]:
        git_sha = getattr(settings, "OMMS_GIT_COMMIT", "") or "unknown"
        return {
            "git_sha": git_sha[:12] if git_sha != "unknown" else "unknown",
            "build_timestamp": getattr(settings, "OMMS_BUILD_TIMESTAMP", "") or "unknown",
            "environment": getattr(settings, "OMMS_ENVIRONMENT_NAME", "") or "unknown",
        }

    def _database_engine_label(self) -> str:
        engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
        if "postgresql" in engine:
            return "postgresql"
        if "sqlite" in engine:
            return "sqlite"
        return engine.rsplit(".", 1)[-1] if engine else "unknown"

    def _database_fingerprint(self) -> str:
        config = connections["default"].settings_dict
        source = "|".join(
            [
                str(config.get("ENGINE", "")),
                str(config.get("HOST", "")),
                str(config.get("PORT", "")),
                str(config.get("NAME", "")),
            ]
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]

    def _migration_status(self) -> dict[str, bool]:
        applied = set(MigrationRecorder(connections["default"]).applied_migrations())
        return {f"{app}.{name}": (app, name) in applied for app, name in REQUIRED_MIGRATIONS}

    def _available_for_requested_dates(self, queryset, *, start_date=None, end_date=None) -> int:
        if not start_date or not end_date:
            return queryset.count()
        service = InventoryAvailabilityService()
        return sum(
            1
            for unit in queryset.prefetch_related(service.booking_prefetch(start_date, end_date))
            if service.resolve(unit, start_date=start_date, end_date=end_date)["status"] == AvailabilityStatus.AVAILABLE
        )

    def _group_exclusions(self, *, all_units, link, final_ids, start_date=None, end_date=None) -> dict[str, int]:
        counters = {
            "unpublished": 0,
            "inactive": 0,
            "wrong_tenant": 0,
            "wrong_city": 0,
            "wrong_region": 0,
            "wrong_inventory_type": 0,
            "invalid_or_missing_location": 0,
            "retired": 0,
            "maintenance": 0,
            "missing_public_id": 0,
            "unavailable_for_dates": 0,
            "serializer_error": 0,
            "other": 0,
        }
        evaluator = PlannerEligibilityEvaluator()
        for unit in all_units.iterator(chunk_size=200):
            reasons = (
                []
                if unit.id in final_ids
                else evaluator.evaluate(unit, link, start_date=start_date, end_date=end_date)["exclusion_reasons"]
            )
            for reason in reasons:
                counters[reason["reason"]] = counters.get(reason["reason"], 0) + 1
        return counters

    def _sample_units(self, *, all_units, link, final_ids, unit_codes, start_date=None, end_date=None) -> list[dict[str, Any]]:
        if unit_codes:
            queryset = all_units.filter(unit_code__in=unit_codes)
        else:
            queryset = all_units.order_by("site__city", "site__name", "unit_code", "id")[:SAMPLE_LIMIT]
        return [
            self._unit_row(unit, link=link, final_ids=final_ids, start_date=start_date, end_date=end_date)
            for unit in queryset[:SAMPLE_LIMIT]
        ]

    def _unit_row(self, unit, *, link, final_ids, start_date=None, end_date=None) -> dict[str, Any]:
        reason = self._exclusion_reason(unit, link=link, final_ids=final_ids, start_date=start_date, end_date=end_date)
        availability = InventoryAvailabilityService().resolve(
            unit,
            start_date=start_date,
            end_date=end_date,
            require_publication=False,
        )
        city_raw = unit.site.city or ""
        return {
            "code": unit.unit_code,
            "tenant_id": unit.site.tenant_id,
            "published": unit.is_publicly_listed,
            "public_id_present": bool(unit.public_id),
            "status": unit.status,
            "availability_status": availability["status"],
            "city_raw": city_raw,
            "city_normalized": city_raw.strip().casefold(),
            "parent_active": True,
            "eligible": unit.id in final_ids,
            "exclusion_reason": reason,
        }

    def _exclusion_reason(self, unit, *, link, final_ids, start_date=None, end_date=None) -> str | None:
        reasons = self._exclusion_reasons(unit, link=link, final_ids=final_ids, start_date=start_date, end_date=end_date)
        return reasons[0]["reason"] if reasons else None

    def _exclusion_reasons(self, unit, *, link, final_ids, start_date=None, end_date=None) -> list[dict[str, Any]]:
        if unit.id in final_ids:
            return []
        reasons = PlannerEligibilityEvaluator().evaluate(unit, link, start_date=start_date, end_date=end_date)["exclusion_reasons"]
        return reasons or [{"reason": "other", "actual": "excluded", "required": "eligible"}]

    def _unit_detail(self, unit, *, link, final_ids, start_date=None, end_date=None) -> dict[str, Any]:
        evaluator = PlannerEligibilityEvaluator()
        evaluation = evaluator.evaluate(unit, link, start_date=start_date, end_date=end_date)
        site = getattr(unit, "site", None)
        reasons = [] if unit.id in final_ids else evaluation["exclusion_reasons"]
        availability = InventoryAvailabilityService().resolve(
            unit,
            start_date=start_date,
            end_date=end_date,
            require_publication=False,
        )
        return {
            "id": unit.id,
            "unit_id": unit.id,
            "unit_code": unit.unit_code,
            "code": unit.unit_code,
            "title": unit.public_description or unit.unit_code,
            "location_id": evaluation["canonical_values"]["location_id"],
            "location_name": evaluation["canonical_values"]["location_name"],
            "location_code": evaluation["canonical_values"]["location_code"],
            "city": evaluation["canonical_values"]["city"],
            "region": evaluation["canonical_values"]["region"],
            "canonical_city": evaluation["canonical_values"]["city"],
            "canonical_region": evaluation["canonical_values"]["region"],
            "unit_city": getattr(unit, "city", None),
            "unit_region": getattr(unit, "region", getattr(unit, "state", None)),
            "inventory_type": evaluation["canonical_values"]["inventory_type"],
            "tenant_id": evaluation["canonical_values"]["tenant_id"],
            "tenant_name": evaluation["canonical_values"]["tenant_name"],
            "published": unit.is_publicly_listed,
            "publicly_listed": unit.is_publicly_listed,
            "status": unit.status,
            "operational_status": unit.status,
            "availability_status": availability["status"],
            "eligible": unit.id in final_ids,
            "exclusion_reasons": reasons,
            "exclusion_reason": reasons[0]["reason"] if reasons else None,
            "actual_value": "; ".join(str(reason["actual"]) for reason in reasons) if reasons else "",
            "required_value": "; ".join(str(reason["required"]) for reason in reasons) if reasons else "",
            "expected_values": evaluation["expected_values"],
            "canonical_values": evaluation["canonical_values"],
            "consistency_warnings": evaluation["consistency_warnings"],
        }

    def _excluded_unit_rows(self, *, all_units, link, final_ids, start_date=None, end_date=None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for unit in all_units.order_by("site__city", "site__name", "unit_code", "id").iterator(chunk_size=200):
            if unit.id in final_ids:
                continue
            rows.append(
                self._unit_detail(unit, link=link, final_ids=final_ids, start_date=start_date, end_date=end_date)
            )
            if len(rows) >= DETAIL_LIMIT:
                break
        return rows
