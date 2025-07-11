# account/views.py
import base64
import json
import logging
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, logout, login, get_user_model
from django.http import JsonResponse
from django.views import View
from account.models import CustomUser, FaceEncoding


class LoginView(View):
    def get(self, request):
        # Login sahifasini render qilish
        return render(request, 'auth/login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            return render(request, 'auth/login.html', {'error': 'Noto‘g‘ri foydalanuvchi nomi yoki parol'})


logger = logging.getLogger(__name__)

class FaceLoginView(View):
    def get(self, request):
        return render(request, 'auth/face_login.html')

    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
            images = data.get('images', [])
            if not images:
                return JsonResponse({
                    'success': False,
                    'error': 'Rasm talab qilinadi',
                    'action': 'retry'
                })

            user = authenticate(request, images=images)
            if user:
                login(request, user, backend='account.backends.FaceAuthBackend')
                request.session.save()
                request.session.modified = True
                next_url = request.GET.get('next', '/')
                return JsonResponse({
                    'success': True,
                    'full_name': user.full_name or 'Ism mavjud emas',
                    'group_name': user.group_name or '',
                    'redirect_url': next_url,
                    'similarity_score': 0.0,
                    'action': 'stop_camera'
                })

            return JsonResponse({
                'success': False,
                'error': 'Yuz ma’lumotlari mos kelmadi',
                'action': 'retry'
            })

        except json.JSONDecodeError:
            logger.error("[ERROR] JSON dekodlash xatosi")
            return JsonResponse({
                'success': False,
                'error': 'Noto‘g‘ri ma’lumot formati',
                'action': 'retry'
            })
        except Exception as e:
            logger.error(f"[ERROR] Umumiy xato: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Xato: {str(e)}',
                'action': 'retry'
            })
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
                redirect('login')
                messages.success(request, "Ro'yxatdan o'tish va tizimga kirish muvaffaqiyatli!")
                return redirect('main')  # Tizimga kirgandan keyin asosiy sahifaga yo'naltirish
            else:
                messages.error(request, "Tizimga avtomatik kirishda xatolik yuz berdi.")

        except Exception as e:
            messages.error(request, f"Ro'yxatdan o'tishda xatolik yuz berdi: {str(e)}")

        return render(request, self.template_name)


def check_username(request):
    username = request.GET.get('username', '').strip()
    is_taken = CustomUser.objects.filter(username=username).exists()
    return JsonResponse({'is_taken': is_taken})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('/account/login/')
