from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from core import settings

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("apps.bot.urls")),
    path(
        "administrator/",
        include(("apps.administrator.urls", "administrator"), namespace="administrator"),
    ),
    path("", include(("apps.landing.urls", "landing"), namespace="landing")),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Only serve static and media files in DEBUG mode
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
