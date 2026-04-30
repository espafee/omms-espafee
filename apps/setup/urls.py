from django.urls import path

from .views import CompanyProfileView, OrganizationEmailSettingsTestView, OrganizationEmailSettingsView

urlpatterns = [
    path("company-profile/", CompanyProfileView.as_view(), name="company-profile"),
    path("email-settings/", OrganizationEmailSettingsView.as_view(), name="organization-email-settings"),
    path("email-settings/test/", OrganizationEmailSettingsTestView.as_view(), name="organization-email-settings-test"),
]
