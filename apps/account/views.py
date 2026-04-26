# account/views.py
import logging

from django.contrib import messages
from django.contrib.auth import authenticate, logout, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View

from apps.account.models import CustomUser


def get_default_redirect(user):
    if user.is_superuser or user.is_staff or getattr(user, "is_teacher", False):
        return reverse("administrator:main")
    return reverse("landing:dashboard")


def auth_context(request, **extra):
    context = {"next": request.GET.get("next") or request.POST.get("next") or ""}
    context.update(extra)
    return context

class LoginView(View):
    def get(self, request):
        return render(request, 'auth/login.html', auth_context(request))

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or get_default_redirect(user)
            return redirect(next_url)
        else:
            return render(
                request,
                'auth/login.html',
                auth_context(request, error="Noto'g'ri foydalanuvchi nomi yoki parol"),
            )


logger = logging.getLogger(__name__)
ID_LOGIN_LENGTHS = {12, 13}



class TwoLoginView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        return render(request, 'auth/two_login.html', {'user_data': user})


class IdLoginView(View):
    template_name = 'auth/id_login.html'
    default_password = 'namdpi451'

    def get(self, request):
        print(f"[DEBUG] GET request received for IdLoginView")
        print(f"[DEBUG] Rendering template: {self.template_name}")
        return render(request, self.template_name, auth_context(request))

    def post(self, request):
        print(f"[DEBUG] POST request received for IdLoginView")
        id_number = request.POST.get('id_number', '').strip()
        print(f"[DEBUG] Received id_number: '{id_number}'")

        # вњ… Boshlang'ich tekshiruvlar
        print(f"[DEBUG] Checking id_number length and format: len={len(id_number)}, isdigit={id_number.isdigit()}")
        if len(id_number) not in ID_LOGIN_LENGTHS or not id_number.isdigit():
            error_message = "ID raqam 12 yoki 13 xonali bo'lishi kerak."
            print(f"[DEBUG] Validation failed: {error_message}")
            return self._error_response(request, error_message)

        # вњ… Foydalanuvchini olish va ruxsat tekshiruvi
        print(f"[DEBUG] Querying CustomUser with username: {id_number}")
        try:
            id_user = CustomUser.objects.get(username=id_number)
            print(f"[DEBUG] User found: {id_user.username}, auth_is_id={id_user.auth_is_id}")
            if not id_user.auth_is_id:
                error_message = "Administrator tomonidan ruxsat berilmagan."
                print(f"[DEBUG] Authorization check failed: {error_message}")
                return self._error_response(request, error_message)
        except CustomUser.DoesNotExist:
            error_message = "Foydalanuvchi topilmadi."
            print(f"[DEBUG] User not found: {error_message}")
            return self._error_response(request, error_message)

        # вњ… Autentifikatsiya qilish
        print(f"[DEBUG] Attempting authentication with username={id_number}, password={self.default_password}")
        user = authenticate(request, username=id_number, password=self.default_password)
        if user is None:
            error_message = "Foydalanuvchi topilmadi yoki parol noto'g'ri."
            print(f"[DEBUG] Authentication failed: {error_message}")
            return self._error_response(request, error_message)

        # вњ… Tizimga kiritish
        print(f"[DEBUG] Authentication successful for user: {user.username}")
        login(request, user)
        next_url = request.POST.get('next') or request.GET.get('next') or reverse('landing:two_login')
        print(f"[DEBUG] Redirecting to: {next_url}")
        return redirect(next_url)

    def _error_response(self, request, message):
        print(f"[DEBUG] Error response triggered: {message}")
        messages.error(request, message)
        return render(request, self.template_name, auth_context(request, error=message))

class RegisterView(View):
    template_name = 'auth/register.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        second_name = request.POST.get('second_name')
        gender = request.POST.get('gender')
        profile_picture = request.FILES.get('profile_picture')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        # Parolni tekshirish
        if password != password_confirm:
            messages.error(request, "Parol va parolni tasdiqlash mos emas!")
            return render(request, self.template_name)

        # Foydalanuvchini yaratish
        try:
            user = CustomUser.objects.create_user(
                username=username,
                first_name=first_name,
                second_name=second_name,
                gender=gender,
                profile_picture=profile_picture,
                password=password,
                is_student=True
            )

            # Foydalanuvchini tizimga avtomatik kiritish
            authenticated_user = authenticate(request, username=username, password=password)
            if authenticated_user:
                login(request, authenticated_user)
                messages.success(request, "Ro'yxatdan o'tish va tizimga kirish muvaffaqiyatli!")
                return redirect(get_default_redirect(authenticated_user))
            else:
                messages.error(request, "Tizimga avtomatik kirishda xatolik yuz berdi.")

        except Exception as e:
            messages.error(request, f"Ro'yxatdan o'tishda xatolik yuz berdi: {str(e)}")

        return render(request, self.template_name)


def check_username(request):
    username = request.GET.get('username', '').strip()
    exclude_user_id = (request.GET.get('exclude_user_id') or '').strip()
    username_queryset = CustomUser.objects.filter(username=username)

    if exclude_user_id.isdigit():
        username_queryset = username_queryset.exclude(id=int(exclude_user_id))

    is_taken = username_queryset.exists()
    return JsonResponse({'is_taken': is_taken})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('landing:login')

