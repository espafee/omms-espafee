from __future__ import annotations

import json
import re
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from apps.inventory.models import MediaUnit

from ...models import MediaPlannerShareLink
from ...serializers import serialize_public_unit
from ...services import InventoryAvailabilityService, PlannerEligibilityEvaluator, planner_unit_queryset


def normalize_unit_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


class Command(BaseCommand):
    help = "Read-only planner inventory reconciliation for specific advertising units."

    def add_arguments(self, parser):
        parser.add_argument("--planner-id", type=int, required=True)
        parser.add_argument("--unit-id", type=int, action="append", default=[])
        parser.add_argument("--unit-code", action="append", default=[])
        parser.add_argument("--start-date")
        parser.add_argument("--end-date")
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        try:
            link = MediaPlannerShareLink.objects.select_related("tenant", "client").get(id=options["planner_id"])
        except MediaPlannerShareLink.DoesNotExist as exc:
            raise CommandError(f"Planner link {options['planner_id']} was not found.") from exc

        requested_codes = [str(code).strip() for code in options["unit_code"] if str(code).strip()]
        requested_ids = [int(unit_id) for unit_id in options["unit_id"]]
        if not requested_codes and not requested_ids:
            raise CommandError("Provide at least one --unit-id or --unit-code.")

        start_date = self._parse_date(options.get("start_date"), "start-date")
        end_date = self._parse_date(options.get("end_date"), "end-date")
        units = self._find_units(requested_ids=requested_ids, requested_codes=requested_codes)
        final_queryset = planner_unit_queryset(link, start_date=start_date, end_date=end_date)
        final_ids = set(final_queryset.values_list("id", flat=True))
        availability_service = InventoryAvailabilityService()
        api_rows = [
            serialize_public_unit(
                unit,
                link=link,
                request=None,
                availability=availability_service.resolve(unit, start_date=start_date, end_date=end_date),
            )
            for unit in final_queryset
        ]
        api_public_ids = {row["public_id"] for row in api_rows}
        evaluator = PlannerEligibilityEvaluator()
        unit_reports = []
        for unit in units:
            evaluation = evaluator.evaluate(unit, link, start_date=start_date, end_date=end_date)
            serialized_public_id = str(unit.public_id)
            unit_reports.append(
                {
                    "unit": self._unit_payload(unit),
                    "gates": self._gate_payload(unit, link, evaluation),
                    "eligible_evaluator": evaluation["eligible"],
                    "final_queryset": unit.id in final_ids,
                    "api_response": serialized_public_id in api_public_ids,
                    "exclusion_reasons": evaluation["exclusion_reasons"],
                    "canonical_values": evaluation["canonical_values"],
                    "expected_values": evaluation["expected_values"],
                    "consistency_warnings": evaluation["consistency_warnings"],
                }
            )

        payload = {
            "planner": self._planner_payload(link),
            "totals": {
                "final_queryset_count": final_queryset.count(),
                "api_response_count": len(api_rows),
                "unique_location_count": final_queryset.values("site_id").distinct().count(),
                "distinct_api_public_ids": len(api_public_ids),
            },
            "requested": {
                "unit_ids": requested_ids,
                "unit_codes": requested_codes,
                "normalized_unit_codes": [normalize_unit_code(code) for code in requested_codes],
            },
            "units": unit_reports,
            "layer_reconciliation": self._layer_reconciliation(unit_reports, final_queryset.count(), len(api_rows)),
        }

        if options["as_json"]:
            self.stdout.write(json.dumps(payload, indent=2, default=str))
            return
        self._write_text(payload)

    def _parse_date(self, value, label):
        if not value:
            return None
        parsed = parse_date(value)
        if not parsed:
            raise CommandError(f"--{label} must use YYYY-MM-DD.")
        return parsed

    def _find_units(self, *, requested_ids: list[int], requested_codes: list[str]):
        units_by_id = {
            unit.id: unit
            for unit in MediaUnit.objects.select_related("site", "site__tenant")
            .prefetch_related("images", "site__images")
            .filter(id__in=requested_ids)
        }
        normalized_requested = {normalize_unit_code(code) for code in requested_codes}
        if normalized_requested:
            for unit in (
                MediaUnit.objects.select_related("site", "site__tenant")
                .prefetch_related("images", "site__images")
                .order_by("unit_code", "id")
            ):
                if normalize_unit_code(unit.unit_code) in normalized_requested:
                    units_by_id[unit.id] = unit
        return list(units_by_id.values())

    def _planner_payload(self, link) -> dict[str, Any]:
        return {
            "id": link.id,
            "title": link.title,
            "tenant_id": link.tenant_id,
            "tenant_name": link.tenant.name,
            "active": link.is_available,
            "revoked": link.is_revoked,
            "expired": link.is_expired,
            "allowed_cities": link.allowed_cities,
            "allowed_regions": link.allowed_regions,
            "allowed_inventory_types": link.allowed_inventory_types,
            "pricing_mode": link.pricing_mode,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
        }

    def _unit_payload(self, unit) -> dict[str, Any]:
        site = unit.site
        return {
            "id": unit.id,
            "unit_code": unit.unit_code,
            "normalized_unit_code": normalize_unit_code(unit.unit_code),
            "title": unit.public_description or unit.unit_code,
            "is_publicly_listed": unit.is_publicly_listed,
            "status": unit.status,
            "inventory_type": unit.site_type,
            "parent_location_id": site.id,
            "parent_location_code": site.code,
            "parent_location_name": site.name,
            "parent_location_tenant_id": site.tenant_id,
            "parent_location_tenant_name": site.tenant.name if site.tenant else "",
            "parent_location_city": site.city,
            "parent_location_region": site.state,
            "parent_location_type": site.site_type,
            "photo_count": unit.images.count(),
            "created_at": unit.created_at,
            "updated_at": unit.updated_at,
        }

    def _gate_payload(self, unit, link, evaluation) -> dict[str, str]:
        reasons = {reason["reason"] for reason in evaluation["exclusion_reasons"]}
        values = evaluation["canonical_values"]
        return {
            "correct_tenant": self._gate(values["tenant_id"] == link.tenant_id, "wrong_tenant", reasons),
            "publicly_listed": self._gate(unit.is_publicly_listed, "unpublished", reasons),
            "not_retired": self._gate(unit.status != MediaUnit.Status.RETIRED, "retired", reasons),
            "city_restriction": self._gate(not link.allowed_cities or "wrong_city" not in reasons, "wrong_city", reasons, active=bool(link.allowed_cities)),
            "region_restriction": self._gate(not link.allowed_regions or "wrong_region" not in reasons, "wrong_region", reasons, active=bool(link.allowed_regions)),
            "inventory_type_restriction": self._gate(not link.allowed_inventory_types or "wrong_inventory_type" not in reasons, "wrong_inventory_type", reasons, active=bool(link.allowed_inventory_types)),
            "parent_location_validity": self._gate(values["location_id"] is not None, "invalid_or_missing_location", reasons),
            "missing_public_id": self._gate(bool(unit.public_id), "missing_public_id", reasons),
        }

    def _gate(self, passed: bool, reason: str, reasons: set[str], *, active: bool = True) -> str:
        if not active:
            return "not_applicable"
        if passed and reason not in reasons:
            return "pass"
        return "fail"

    def _layer_reconciliation(self, unit_reports, final_count: int, api_count: int):
        rows = []
        for label, key, count in [
            ("Database", "unit", len(unit_reports)),
            ("Eligible evaluator", "eligible_evaluator", sum(1 for row in unit_reports if row["eligible_evaluator"])),
            ("Final queryset", "final_queryset", final_count),
            ("API response", "api_response", api_count),
        ]:
            row = {"layer": label, "count": count}
            for report in unit_reports:
                code = report["unit"]["normalized_unit_code"]
                if key == "unit":
                    row[code] = "present"
                else:
                    row[code] = "present" if report[key] else "missing"
            rows.append(row)
        return rows

    def _write_text(self, payload):
        self.stdout.write("Planner")
        self.stdout.write(json.dumps(payload["planner"], indent=2, default=str))
        self.stdout.write("Totals")
        self.stdout.write(json.dumps(payload["totals"], indent=2, default=str))
        self.stdout.write("Layer reconciliation")
        for row in payload["layer_reconciliation"]:
            self.stdout.write(json.dumps(row, default=str))
        self.stdout.write("Units")
        for report in payload["units"]:
            self.stdout.write(json.dumps(report, indent=2, default=str))
