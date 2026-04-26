from django.http import HttpResponseForbidden
from django.contrib.auth.views import redirect_to_login
from django.urls import Resolver404, resolve

from core.error_views import render_error_page


class AdministratorAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return self.get_response(request)

        if "administrator" in match.namespaces:
            user = request.user
            url_name = match.url_name or ""

            is_help_url = url_name.startswith("help") or url_name in {
                "delete-help-plan",
                "delete-all-help-plans",
            }
            if is_help_url:
                if not user.is_authenticated or not getattr(user, "is_help", False):
                    return render_error_page(request, status_code=404)
                return self.get_response(request)

            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            if not (user.is_superuser or user.is_staff or getattr(user, "is_teacher", False)):
                return HttpResponseForbidden("Administrator bo'limiga kirish ruxsati yo'q.")

        return self.get_response(request)
