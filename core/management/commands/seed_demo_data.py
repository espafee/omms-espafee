from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.models import Invoice, Payment
from apps.bookings.models import Booking
from apps.campaigns.models import Campaign, CampaignAsset
from apps.inventory.models import MediaSite, MediaUnit, RateCard
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia


class Command(BaseCommand):
    help = "Seed demo data for local frontend/backend development."

    def handle(self, *args, **options):
        user_model = get_user_model()
        today = timezone.localdate()

        admin_user, _ = user_model.objects.get_or_create(
            email="demo@example.com",
            defaults={
                "username": "demo_admin",
                "role": "admin",
                "is_staff": True,
                "organization_name": "Outdoor Media Demo",
            },
        )
        admin_user.role = "admin"
        admin_user.is_staff = True
        admin_user.organization_name = "Outdoor Media Demo"
        admin_user.set_password("DemoPass123!")
        admin_user.save()

        client_user, _ = user_model.objects.get_or_create(
            email="client@example.com",
            defaults={
                "username": "demo_client",
                "role": "client",
                "organization_name": "Skyline Foods",
            },
        )
        client_user.role = "client"
        client_user.organization_name = "Skyline Foods"
        client_user.set_password("ClientPass123!")
        client_user.save()

        site_one, _ = MediaSite.objects.get_or_create(
            code="DEMO-SITE-001",
            defaults={
                "name": "Airport Arrival Billboard",
                "site_type": MediaSite.SiteType.BILLBOARD,
                "address": "Airport Corridor",
                "city": "Pune",
                "state": "Maharashtra",
                "owner": admin_user,
            },
        )
        site_two, _ = MediaSite.objects.get_or_create(
            code="DEMO-SITE-002",
            defaults={
                "name": "Metro Digital Panel",
                "site_type": MediaSite.SiteType.DIGITAL,
                "address": "Central Metro Plaza",
                "city": "Mumbai",
                "state": "Maharashtra",
                "owner": admin_user,
            },
        )

        unit_one, _ = MediaUnit.objects.get_or_create(
            unit_code="DEMO-UNIT-001",
            defaults={
                "site": site_one,
                "face_count": 1,
                "width": Decimal("20.00"),
                "height": Decimal("10.00"),
                "status": MediaUnit.Status.AVAILABLE,
                "is_illuminated": True,
                "monthly_rate": Decimal("50000.00"),
            },
        )
        unit_two, _ = MediaUnit.objects.get_or_create(
            unit_code="DEMO-UNIT-002",
            defaults={
                "site": site_two,
                "face_count": 2,
                "width": Decimal("18.00"),
                "height": Decimal("9.00"),
                "status": MediaUnit.Status.RESERVED,
                "is_illuminated": False,
                "monthly_rate": Decimal("65000.00"),
            },
        )

        RateCard.objects.get_or_create(
            unit=unit_one,
            start_date=today,
            end_date=today + timedelta(days=30),
            defaults={
                "base_rate": Decimal("50000.00"),
                "tax_percentage": Decimal("18.00"),
            },
        )
        RateCard.objects.get_or_create(
            unit=unit_two,
            start_date=today,
            end_date=today + timedelta(days=30),
            defaults={
                "base_rate": Decimal("65000.00"),
                "tax_percentage": Decimal("18.00"),
            },
        )

        campaign, _ = Campaign.objects.get_or_create(
            code="DEMO-CAMP-001",
            defaults={
                "name": "Summer Visibility Blast",
                "client": client_user,
                "account_manager": admin_user,
                "start_date": today,
                "end_date": today + timedelta(days=21),
                "budget": Decimal("150000.00"),
                "status": Campaign.Status.ACTIVE,
                "objective": "Increase citywide brand reach",
            },
        )

        CampaignAsset.objects.get_or_create(
            campaign=campaign,
            name="Launch Creative",
            defaults={
                "asset_type": "image",
                "file_url": "https://example.com/assets/demo-launch.jpg",
                "version": "v1",
                "is_approved": True,
            },
        )

        booking, _ = Booking.objects.get_or_create(
            campaign=campaign,
            media_unit=unit_two,
            start_date=today,
            end_date=today + timedelta(days=21),
            defaults={
                "booked_rate": Decimal("70000.00"),
                "status": Booking.Status.CONFIRMED,
                "remarks": "Seeded demo booking",
            },
        )

        poe_record, _ = ProofOfExecution.objects.get_or_create(
            booking=booking,
            executed_on=today,
            defaults={
                "checked_by": admin_user,
                "verification_status": ProofOfExecution.VerificationStatus.VERIFIED,
                "notes": "Seeded for frontend demo",
            },
        )

        ProofOfExecutionMedia.objects.get_or_create(
            poe_record=poe_record,
            media_url="https://example.com/assets/demo-poe.jpg",
            defaults={
                "media_type": "image",
                "captured_at": timezone.now(),
            },
        )

        invoice, _ = Invoice.objects.get_or_create(
            invoice_number="DEMO-INV-001",
            defaults={
                "campaign": campaign,
                "issue_date": today,
                "due_date": today + timedelta(days=14),
                "subtotal": Decimal("70000.00"),
                "tax_amount": Decimal("12600.00"),
                "total_amount": Decimal("82600.00"),
                "status": Invoice.Status.ISSUED,
            },
        )

        Payment.objects.get_or_create(
            invoice=invoice,
            reference_number="DEMO-PAY-001",
            defaults={
                "payment_date": today,
                "amount": Decimal("25000.00"),
                "method": Payment.Method.BANK_TRANSFER,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
        self.stdout.write("Admin login: demo@example.com / DemoPass123!")
