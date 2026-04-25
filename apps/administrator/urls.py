from django.urls import include, path


app_name = "administrator"

urlpatterns = [
    path("", include("apps.question.urls")),
    path("logs/", include("apps.logs.urls")),
]
