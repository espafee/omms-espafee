from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from rest_framework import serializers

from .models import CompanyProfile, OrganizationEmailSettings


class SetupService:
    @staticmethod
    def get_company_profile() -> CompanyProfile:
        profile, _ = CompanyProfile.objects.get_or_create(singleton_key=1)
        return profile

    @staticmethod
    def get_email_settings() -> OrganizationEmailSettings:
        email_settings, _ = OrganizationEmailSettings.objects.get_or_create(singleton_key=1)
        return email_settings

    @classmethod
    @transaction.atomic
    def update_company_profile(cls, **validated_data) -> CompanyProfile:
        profile = cls.get_company_profile()
        for field, value in validated_data.items():
            setattr(profile, field, value)
        profile.save()
        return profile

    @classmethod
    @transaction.atomic
    def update_email_settings(cls, *, smtp_password: str | None = None, **validated_data) -> OrganizationEmailSettings:
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
