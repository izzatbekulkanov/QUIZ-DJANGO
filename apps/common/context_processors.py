import os

from django.urls import reverse

from apps.question.models import SystemSetting


def build_office_helper_session_payload(request, setting=None):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    if not request.session.session_key:
        request.session.save()

    return {
        'session_key': request.session.session_key,
        'user_id': user.id,
        'username': user.get_username(),
        'full_name': getattr(user, 'full_name', '') or user.get_full_name(),
        'email': getattr(user, 'email', ''),
        'django_host': request.get_host(),
        'system_origin': request.build_absolute_uri('/').rstrip('/'),
        'system_label': getattr(setting, 'name', '') if setting else request.get_host(),
        'page_url': request.build_absolute_uri(),
        'expires_in_seconds': request.session.get_expiry_age(),
    }


def system_settings(request):
    setting = SystemSetting.objects.filter(is_active=True).first()
    context = {
        'system': setting,
        'office_helper_base_url': os.environ.get("QUIZ_OFFICE_HELPER_URL", "http://127.0.0.1:8765"),
        'office_helper_logout_signal': request.GET.get("helper_logout") == "1",
        'office_helper_session_state_url': reverse("landing:office-helper-session-state"),
        'office_helper_session': {},
    }

    context['office_helper_session'] = build_office_helper_session_payload(request, setting)

    return context
