from django.urls import include, path


app_name = "landing"

urlpatterns = [
    path("auth/", include("apps.account.urls")),
    path("", include("apps.dashboard.urls")),
]
