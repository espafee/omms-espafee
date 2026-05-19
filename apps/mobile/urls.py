from django.urls import path

from .views import (
    AssignedWorkView,
    MobileAdminAlertsView,
    MobileAdminDailyActivityView,
    MobileAdminIssuesView,
    MobileAdminOverviewView,
    MobileAdminPoeTrackerView,
    MobileAdminRunningCampaignsView,
    MobileAdminSearchView,
    MobilePoeSubmitView,
)

urlpatterns = [
    path("assigned-work/", AssignedWorkView.as_view(), name="mobile-assigned-work"),
    path("poe/submit/", MobilePoeSubmitView.as_view(), name="mobile-poe-submit"),
    path("admin/overview/", MobileAdminOverviewView.as_view(), name="mobile-admin-overview"),
    path("admin/running-campaigns/", MobileAdminRunningCampaignsView.as_view(), name="mobile-admin-running-campaigns"),
    path("admin/poe-tracker/", MobileAdminPoeTrackerView.as_view(), name="mobile-admin-poe-tracker"),
    path("admin/daily-activity/", MobileAdminDailyActivityView.as_view(), name="mobile-admin-daily-activity"),
    path("admin/alerts/", MobileAdminAlertsView.as_view(), name="mobile-admin-alerts"),
    path("admin/search/", MobileAdminSearchView.as_view(), name="mobile-admin-search"),
    path("admin/issues/", MobileAdminIssuesView.as_view(), name="mobile-admin-issues"),
]
