from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMessage, get_connection
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .models import CompanyProfile, OrganizationEmailSettings, SetupAuditLog


class SetupService:
    @staticmethod
    def get_company_profile() -> CompanyProfile:
        profile, _ = CompanyProfile.objects.get_or_create(singleton_key=1)
        return profile

    @staticmethod
    def get_email_settings() -> OrganizationEmailSettings:
        email_settings, _ = OrganizationEmailSettings.objects.get_or_create(singleton_key=1)
        return email_settings

    @staticmethod
    def is_effectively_locked(profile: CompanyProfile | None = None) -> bool:
        profile = profile or SetupService.get_company_profile()
        if profile.setup_status != CompanyProfile.SetupStatus.SUBMITTED:
            return False
        if profile.setup_locked:
            return True
        return not profile.setup_unlocked_until or profile.setup_unlocked_until <= timezone.now()

    @staticmethod
    def _audit(action: str, *, actor=None, message: str = "") -> None:
        SetupAuditLog.objects.create(action=action, actor=actor if getattr(actor, "is_authenticated", False) else None, message=message[:255])

    @classmethod
    def _ensure_setup_editable(cls) -> None:
        if cls.is_effectively_locked():
            raise PermissionDenied("Setup is locked. Request an email OTP unlock before making changes.")

    @classmethod
    def get_setup_status(cls) -> dict:
        profile = cls.get_company_profile()
        locked = cls.is_effectively_locked(profile)
        return {
            "setup_status": profile.setup_status,
            "setup_locked": locked,
            "setup_unlocked_until": profile.setup_unlocked_until if not locked else None,
            "setup_unlock_otp_expires_at": profile.setup_unlock_otp_expires_at,
            "setup_unlock_attempts": profile.setup_unlock_attempts,
            "max_unlock_attempts": 3,
        }

    @classmethod
    @transaction.atomic
    def update_company_profile(cls, *, actor=None, **validated_data) -> CompanyProfile:
        cls._ensure_setup_editable()
        profile = cls.get_company_profile()
        for field, value in validated_data.items():
            setattr(profile, field, value)
        profile.save()
        return profile

    @classmethod
    @transaction.atomic
    def update_email_settings(
        cls,
        *,
        actor=None,
        smtp_password: str | None = None,
        **validated_data,
    ) -> OrganizationEmailSettings:
        cls._ensure_setup_editable()
        email_settings = cls.get_email_settings()
        verification_needs_reset = False

        for field, value in validated_data.items():
            if getattr(email_settings, field) != value:
                verification_needs_reset = True
            setattr(email_settings, field, value)

        if smtp_password is not None:
            verification_needs_reset = True
            try:
                if smtp_password:
                    email_settings.set_smtp_password(smtp_password)
                else:
                    email_settings.clear_smtp_password()
            except ImproperlyConfigured as exc:
                raise serializers.ValidationError({"smtp_password": [str(exc)]}) from exc

        if verification_needs_reset:
            email_settings.email_verified = False

        email_settings.save()
        return email_settings

    @classmethod
    @transaction.atomic
    def submit_setup(cls, *, actor=None) -> dict:
        profile = cls.get_company_profile()
        profile.setup_status = CompanyProfile.SetupStatus.SUBMITTED
        profile.setup_locked = True
        profile.setup_unlocked_until = None
        profile.setup_unlock_otp_hash = ""
        profile.setup_unlock_otp_expires_at = None
        profile.setup_unlock_attempts = 0
        profile.save(
            update_fields=[
                "setup_status",
                "setup_locked",
                "setup_unlocked_until",
                "setup_unlock_otp_hash",
                "setup_unlock_otp_expires_at",
                "setup_unlock_attempts",
                "updated_at",
            ]
        )
        cls._audit(SetupAuditLog.Action.SUBMITTED, actor=actor, message="Setup submitted and locked.")
        return cls.get_setup_status()

    @classmethod
    @transaction.atomic
    def lock_setup(cls, *, actor=None) -> dict:
        profile = cls.get_company_profile()
        profile.setup_status = CompanyProfile.SetupStatus.SUBMITTED
        profile.setup_locked = True
        profile.setup_unlocked_until = None
        profile.setup_unlock_otp_hash = ""
        profile.setup_unlock_otp_expires_at = None
        profile.setup_unlock_attempts = 0
        profile.save(
            update_fields=[
                "setup_status",
                "setup_locked",
                "setup_unlocked_until",
                "setup_unlock_otp_hash",
                "setup_unlock_otp_expires_at",
                "setup_unlock_attempts",
                "updated_at",
            ]
        )
        cls._audit(SetupAuditLog.Action.LOCKED, actor=actor, message="Setup locked.")
        return cls.get_setup_status()

    @classmethod
    @transaction.atomic
    def request_unlock_otp(cls, *, actor) -> dict:
        profile = cls.get_company_profile()
        recipient_email = getattr(actor, "email", "") or profile.communication_email
        if not recipient_email:
            raise serializers.ValidationError({"detail": "A Super Admin email address is required to send an unlock OTP."})

        otp = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = timezone.now() + timezone.timedelta(minutes=10)
        profile.setup_unlock_requested_at = timezone.now()
        profile.setup_unlock_otp_hash = make_password(otp)
        profile.setup_unlock_otp_expires_at = expires_at
        profile.setup_unlock_attempts = 0
        profile.save(
            update_fields=[
                "setup_unlock_requested_at",
                "setup_unlock_otp_hash",
                "setup_unlock_otp_expires_at",
                "setup_unlock_attempts",
                "updated_at",
            ]
        )

        subject = f"{profile.branding_name} setup unlock OTP"
        body = (
            "Use this OTP to unlock your OMMS setup page.\n\n"
            f"OTP: {otp}\n\n"
            "This OTP expires in 10 minutes. If you did not request this, ignore this email."
        )
        email_settings = cls.get_email_settings()
        from_email = email_settings.from_email or settings.DEFAULT_FROM_EMAIL
        reply_to = [email_settings.reply_to_email] if email_settings.reply_to_email else None
        EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[recipient_email],
            reply_to=reply_to,
            connection=get_connection(),
        ).send(fail_silently=False)
        cls._audit(SetupAuditLog.Action.OTP_REQUESTED, actor=actor, message="Setup unlock OTP requested.")
        return {
            "status": "otp_sent",
            "expires_at": expires_at,
        }

    @classmethod
    def verify_unlock_otp(cls, *, actor, otp: str) -> dict:
        profile = cls.get_company_profile()
        now = timezone.now()
        if not profile.setup_unlock_otp_hash or not profile.setup_unlock_otp_expires_at:
            cls._audit(SetupAuditLog.Action.OTP_FAILED, actor=actor, message="OTP verification failed: no active OTP.")
            raise serializers.ValidationError({"otp": ["Request a new OTP before verifying."]})
        if profile.setup_unlock_otp_expires_at <= now:
            cls._audit(SetupAuditLog.Action.OTP_FAILED, actor=actor, message="OTP verification failed: expired OTP.")
            raise serializers.ValidationError({"otp": ["This OTP has expired. Request a new OTP."]})
        if profile.setup_unlock_attempts >= 3:
            cls._audit(SetupAuditLog.Action.OTP_FAILED, actor=actor, message="OTP verification failed: max attempts reached.")
            raise serializers.ValidationError({"otp": ["Too many failed attempts. Request a new OTP."]})

        if not check_password(otp, profile.setup_unlock_otp_hash):
            profile.setup_unlock_attempts += 1
            profile.save(update_fields=["setup_unlock_attempts", "updated_at"])
            cls._audit(SetupAuditLog.Action.OTP_FAILED, actor=actor, message="OTP verification failed: invalid OTP.")
            raise serializers.ValidationError({"otp": ["Invalid OTP."]})

        profile.setup_locked = False
        profile.setup_unlocked_until = now + timezone.timedelta(minutes=30)
        profile.setup_unlock_otp_hash = ""
        profile.setup_unlock_otp_expires_at = None
        profile.setup_unlock_attempts = 0
        profile.save(
            update_fields=[
                "setup_locked",
                "setup_unlocked_until",
                "setup_unlock_otp_hash",
                "setup_unlock_otp_expires_at",
                "setup_unlock_attempts",
                "updated_at",
            ]
        )
        cls._audit(SetupAuditLog.Action.OTP_VERIFIED, actor=actor, message="Setup unlock OTP verified.")
        cls._audit(SetupAuditLog.Action.UNLOCKED, actor=actor, message="Setup temporarily unlocked.")
        return cls.get_setup_status()

    @classmethod
    def send_test_email(cls, *, recipient_email: str | None = None) -> str:
        company_profile = cls.get_company_profile()
        email_settings = cls.get_email_settings()
        target_email = (
            recipient_email
            or company_profile.communication_email
            or email_settings.reply_to_email
            or email_settings.from_email
        )
        if not target_email:
            raise serializers.ValidationError(
                {"recipient_email": ["Add a communication email or provide a recipient email first."]}
            )

        subject = f"{company_profile.branding_name} SMTP verification"
        body = (
            "This is a test email from your OMMS organization setup.\n\n"
            "If you received this message, your SMTP configuration is working."
        )
        from_email = email_settings.from_email or settings.DEFAULT_FROM_EMAIL
        reply_to = [email_settings.reply_to_email] if email_settings.reply_to_email else None
        connection = cls._build_email_connection(email_settings)

        message = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[target_email],
            reply_to=reply_to,
            connection=connection,
        )
        try:
            message.send(fail_silently=False)
        except Exception:
            email_settings.email_verified = False
            email_settings.save(update_fields=["email_verified", "updated_at"])
            raise

        email_settings.email_verified = True
        email_settings.save(update_fields=["email_verified", "updated_at"])
        return target_email

    @staticmethod
    def _build_email_connection(email_settings: OrganizationEmailSettings):
        backend = settings.EMAIL_BACKEND
        if backend != "django.core.mail.backends.smtp.EmailBackend":
            return get_connection(backend=backend)

        if not email_settings.smtp_host:
            raise serializers.ValidationError({"smtp_host": ["SMTP host is required before sending a test email."]})
        if not email_settings.from_email:
            raise serializers.ValidationError({"from_email": ["From email is required before sending a test email."]})

        try:
            password = email_settings.get_smtp_password() if email_settings.smtp_password_encrypted else ""
        except ImproperlyConfigured as exc:
            raise serializers.ValidationError({"smtp_password": [str(exc)]}) from exc

        return get_connection(
            backend=backend,
            host=email_settings.smtp_host,
            port=email_settings.smtp_port,
            username=email_settings.smtp_username,
            password=password,
            use_tls=email_settings.use_tls,
            use_ssl=email_settings.use_ssl,
        )
