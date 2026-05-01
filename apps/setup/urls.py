from django.urls import path

from .views import (
    CompanyProfileView,
    OrganizationEmailSettingsTestView,
    OrganizationEmailSettingsView,
    SetupLockView,
    SetupStatusView,
    SetupSubmitView,
    SetupUnlockRequestOtpView,
    SetupUnlockVerifyOtpView,
)

urlpatterns = [
    path("status/", SetupStatusView.as_view(), name="setup-status"),
    path("submit/", SetupSubmitView.as_view(), name="setup-submit"),
    path("unlock/request-otp/", SetupUnlockRequestOtpView.as_view(), name="setup-unlock-request-otp"),
    path("unlock/verify-otp/", SetupUnlockVerifyOtpView.as_view(), name="setup-unlock-verify-otp"),
    path("lock/", SetupLockView.as_view(), name="setup-lock"),
    path("company-profile/", CompanyProfileView.as_view(), name="company-profile"),
    path("email-settings/", OrganizationEmailSettingsView.as_view(), name="organization-email-settings"),
    path("email-settings/test/", OrganizationEmailSettingsTestView.as_view(), name="organization-email-settings-test"),
]
