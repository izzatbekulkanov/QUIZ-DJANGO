from django.contrib import admin
from django.urls import path, re_path, include
from django.conf.urls.static import static
from core import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('account/', include('account.urls')),  # Added account app URLs
    path('api/', include('bot.urls')),  # Added account app URLs
    path('', include('dashboard.urls')),
    path('question/', include('question.urls')),  # Added question app URLs
    path('logs/', include('logs.urls')),  # Added question app URLs
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Only serve static and media files in DEBUG mode
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)