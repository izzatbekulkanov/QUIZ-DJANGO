from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.media_views import serve_media_file
from core import settings

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("media/<path:path>", serve_media_file, name="serve-media-file"),
    path("api/", include("apps.bot.urls")),
    path(
        "administrator/",
        include(("apps.administrator.urls", "administrator"), namespace="administrator"),
    ),
    path("", include(("apps.landing.urls", "landing"), namespace="landing")),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler400 = "core.error_views.bad_request"
handler403 = "core.error_views.permission_denied"
handler404 = "core.error_views.page_not_found"
handler500 = "core.error_views.server_error"
