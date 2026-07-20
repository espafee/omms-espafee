from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.inventory.models import MediaUnit
from apps.tenants.models import Tenant
from apps.tenants.services import get_user_tenant, is_platform_super_admin
from apps.users.models import User

from .models import CampaignProposal, CampaignProposalLine, MediaPlannerShareLink


class MediaPlannerShareLinkSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    client_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)
    effective_show_rates = serializers.BooleanField(read_only=True)
    eligible_unit_count = serializers.SerializerMethodField()

    class Meta:
        model = MediaPlannerShareLink
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "client",
            "client_name",
            "title",
            "allowed_cities",
            "allowed_regions",
            "allowed_inventory_types",
            "show_rates",
            "pricing_mode",
            "effective_show_rates",
            "eligible_unit_count",
            "allow_proposal_submission",
            "allow_image_download",
            "allow_map_data",
            "expires_at",
            "revoked_at",
            "last_accessed_at",
            "token_prefix",
            "public_path",
            "created_by_name",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_name",
            "client_name",
            "effective_show_rates",
            "eligible_unit_count",
            "revoked_at",
            "last_accessed_at",
            "token_prefix",
            "public_path",
            "created_by_name",
            "is_available",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "tenant": {"required": False},
            "client": {"required": False},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        if not actor or not getattr(actor, "is_authenticated", False):
            return
        if not is_platform_super_admin(actor):
            tenant = get_user_tenant(actor)
            self.fields["tenant"].queryset = Tenant.objects.filter(pk=getattr(tenant, "id", None))
            self.fields["client"].queryset = User.objects.filter(tenant=tenant, role=User.Role.CLIENT)
        else:
            self.fields["tenant"].queryset = Tenant.objects.filter(tenant_type=Tenant.TenantType.CLIENT)
            self.fields["client"].queryset = User.objects.filter(role=User.Role.CLIENT, tenant__tenant_type=Tenant.TenantType.CLIENT)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        submitted_tenant = attrs.get("tenant")
        if is_platform_super_admin(actor):
            if self.instance is None and not submitted_tenant:
                raise serializers.ValidationError({"tenant": ["Select a client company for this planner link."]})
            tenant = submitted_tenant or getattr(self.instance, "tenant", None)
            if tenant and tenant.tenant_type != Tenant.TenantType.CLIENT:
                raise serializers.ValidationError({"tenant": ["Select a client company, not the platform tenant."]})
        else:
            tenant = get_user_tenant(actor)
            if submitted_tenant and submitted_tenant != tenant:
                raise serializers.ValidationError({"tenant": ["You can only create planner links for your own company."]})
            if tenant:
                attrs["tenant"] = tenant
        client = attrs.get("client")
        if client and client.tenant_id != getattr(tenant, "id", None):
            raise serializers.ValidationError({"client": ["Client must belong to the selected company."]})
        expires_at = attrs.get("expires_at")
        if expires_at and expires_at <= timezone.now():
            raise serializers.ValidationError({"expires_at": ["Expiry must be in the future."]})
        for field in ("allowed_cities", "allowed_regions", "allowed_inventory_types"):
            if field in attrs and not isinstance(attrs[field], list):
                raise serializers.ValidationError({field: ["Use a list of allowed values."]})
        return attrs

    def get_client_name(self, obj):
        if not obj.client:
            return ""
        return obj.client.organization_name or obj.client.get_full_name() or obj.client.email

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return ""
        return obj.created_by.get_full_name() or obj.created_by.email

    def get_eligible_unit_count(self, obj):
        from .services import planner_unit_queryset

        return planner_unit_queryset(obj).count()


class CampaignProposalLineSerializer(serializers.ModelSerializer):
    current_availability = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = CampaignProposalLine
        fields = [
            "id",
            "unit_public_id",
            "unit_code",
            "location_name",
            "public_address",
            "city",
            "region",
            "width",
            "height",
            "facing_direction",
            "display_format",
            "is_illuminated",
            "monthly_rate_snapshot",
            "tax_rate_snapshot",
            "availability_status",
            "availability_snapshot",
            "current_availability",
            "photo_url",
        ]
        read_only_fields = fields

    def get_current_availability(self, obj):
        from .services import InventoryAvailabilityService

        if not obj.media_unit:
            return {"status": "unavailable", "label": "Unavailable", "reason": "Unit no longer exists."}
        proposal = obj.proposal
        return InventoryAvailabilityService().resolve(
            obj.media_unit,
            start_date=proposal.requested_start_date,
            end_date=proposal.requested_end_date,
        )

    def get_photo_url(self, obj):
        if not obj.media_unit:
            return None
        image = obj.media_unit.primary_image_object or obj.media_unit.site.primary_image_object
        if not image:
            return None
        return image.image_url(request=self.context.get("request"), variant="planner_card")


class CampaignProposalSerializer(serializers.ModelSerializer):
    lines = CampaignProposalLineSerializer(many=True, read_only=True)
    client_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    estimate_number = serializers.CharField(source="estimate.estimate_number", read_only=True)
    converted_campaign_code = serializers.CharField(source="converted_campaign.code", read_only=True)
    audit_events = serializers.SerializerMethodField()

    class Meta:
        model = CampaignProposal
        fields = [
            "id",
            "reference",
            "tenant",
            "share_link",
            "client",
            "client_name",
            "campaign_name",
            "brand_company",
            "objective",
            "requested_start_date",
            "requested_end_date",
            "contact_name",
            "contact_email",
            "contact_phone",
            "billing_gstin",
            "billing_details",
            "notes",
            "source",
            "status",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "assigned_to",
            "assigned_to_name",
            "preliminary_subtotal",
            "selected_unit_count",
            "availability_conflict_count",
            "estimate",
            "estimate_number",
            "converted_campaign",
            "converted_campaign_code",
            "lines",
            "audit_events",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_client_name(self, obj):
        if not obj.client:
            return obj.brand_company or obj.contact_name
        return obj.client.organization_name or obj.client.get_full_name() or obj.client.email

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return "Unassigned"
        return obj.assigned_to.get_full_name() or obj.assigned_to.email

    def get_audit_events(self, obj):
        from apps.observability.models import AuditEvent

        events = AuditEvent.objects.filter(entity_type="campaignproposal", entity_id=str(obj.id)).select_related("actor")[:50]
        return [
            {
                "event_type": event.event_type,
                "summary": event.summary,
                "severity": event.severity,
                "actor": event.actor.get_full_name() or event.actor.email if event.actor else "System",
                "created_at": event.created_at,
            }
            for event in events
        ]


class PublicProposalSubmitSerializer(serializers.Serializer):
    campaign_name = serializers.CharField(max_length=255)
    brand_company = serializers.CharField(max_length=255, required=False, allow_blank=True)
    objective = serializers.CharField(required=False, allow_blank=True)
    requested_start_date = serializers.DateField()
    requested_end_date = serializers.DateField()
    contact_name = serializers.CharField(max_length=255)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    billing_gstin = serializers.CharField(max_length=15, required=False, allow_blank=True)
    billing_details = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    unit_public_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False, max_length=100)
    idempotency_key = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["requested_end_date"] < attrs["requested_start_date"]:
            raise serializers.ValidationError({"requested_end_date": ["End date must be on or after start date."]})
        return attrs


class ProposalStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        CampaignProposal.Status.UNDER_REVIEW,
        CampaignProposal.Status.AVAILABILITY_CONFIRMED,
        CampaignProposal.Status.CLIENT_REJECTED,
        CampaignProposal.Status.EXPIRED,
    ])


class ProposalAssignmentSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True)

    def validate_assigned_to(self, value):
        proposal = self.context["proposal"]
        if value and value.tenant_id != proposal.tenant_id:
            raise serializers.ValidationError("Owner must belong to the proposal company.")
        return value


class ProposalEstimateSerializer(serializers.Serializer):
    client = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.CLIENT), required=False)

    def validate_client(self, value):
        proposal = self.context["proposal"]
        if value.tenant_id != proposal.tenant_id:
            raise serializers.ValidationError("Client must belong to the proposal company.")
        return value


class ProposalConversionSerializer(serializers.Serializer):
    campaign_code = serializers.CharField(max_length=50)


def serialize_public_unit(unit, *, link, request, availability):
    images = list(unit.images.all()) or list(unit.site.images.all())
    public_images = [
        {
            "url": image.image_url(request=request, variant="planner_card"),
            "caption": image.caption,
            "is_primary": image.is_primary,
        }
        for image in images
        if image.image_url(request=request, variant="planner_card")
    ]
    public_images.sort(key=lambda item: (not item["is_primary"], item["caption"]))
    payload = {
        "public_id": str(unit.public_id),
        "unit_code": unit.unit_code,
        "location_name": unit.site.name,
        "public_address": unit.site.address,
        "city": unit.site.city,
        "region": unit.site.state,
        "dimensions": {"width": str(unit.width), "height": str(unit.height)},
        "display_format": unit.site_type,
        "facing_direction": unit.facing_direction,
        "is_illuminated": unit.is_illuminated,
        "availability": availability,
        "description": unit.public_description,
        "features": unit.public_features if isinstance(unit.public_features, list) else [],
        "primary_photo": public_images[0] if public_images else None,
        "photos": public_images,
        "image_download_allowed": link.allow_image_download,
        "monthly_rate": str(unit.monthly_rate) if link.effective_show_rates else None,
    }
    if link.allow_map_data and unit.site.location_status == unit.site.LocationStatus.VERIFIED:
        payload["map"] = {
            "latitude": str(unit.site.latitude) if unit.site.latitude is not None else None,
            "longitude": str(unit.site.longitude) if unit.site.longitude is not None else None,
        }
    return payload
