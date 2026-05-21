import json

from django.core.management.base import BaseCommand

from apps.tenants.identifier_audit import build_tenant_identifier_audit


class Command(BaseCommand):
    help = "Audit tenant-scoped identifier and sequence migration readiness without changing data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="Output format.",
        )

    def handle(self, *args, **options):
        audit = build_tenant_identifier_audit()
        if options["format"] == "json":
            self.stdout.write(json.dumps(audit, indent=2, default=str))
            return

        self.stdout.write("OMMS Tenant Identifier Audit - Phase 1F")
        self.stdout.write("=" * 44)
        self.stdout.write(f"Constraints changed: {audit['constraints_changed']}")
        self.stdout.write(f"Numbering behavior changed: {audit['numbering_behavior_changed']}")
        self.stdout.write("")

        self.stdout.write("Identifier targets")
        for target in audit["identifier_targets"]:
            duplicate_count = len(target["duplicate_groups"])
            self.stdout.write(
                f"- {target['model']}.{target['field']}: records={target['record_count']}, "
                f"null_tenant={target['null_tenant_count']}, duplicate_groups={duplicate_count}"
            )
            if duplicate_count:
                for group in target["duplicate_groups"]:
                    self.stdout.write(
                        f"  * {group['identifier']}: rows={group['row_count']}, "
                        f"tenants={group['tenant_count']}, risk={group['risk']}"
                    )

        self.stdout.write("")
        self.stdout.write("Null tenant checks")
        for item in audit["null_tenant_records"]:
            self.stdout.write(f"- {item['model']} via {item['tenant_path']}: {item['null_tenant_count']}")

        self.stdout.write("")
        self.stdout.write("Sequence ownership gaps")
        for item in audit["sequence_ownership_gaps"]:
            self.stdout.write(f"- {item['model']} ({item['key']}): {item['risk']}")

        self.stdout.write("")
        self.stdout.write("Phase 1G recommendation")
        for item in audit["phase_1g_recommendation"]:
            self.stdout.write(f"- {item}")
