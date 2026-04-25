from django.http import HttpResponseForbidden
from django.contrib.auth.views import redirect_to_login
from django.urls import Resolver404, resolve


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

            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            if not (user.is_superuser or user.is_staff or getattr(user, "is_teacher", False)):
                return HttpResponseForbidden("Administrator bo'limiga kirish ruxsati yo'q.")

        return self.get_response(request)
