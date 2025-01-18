# account/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, logout, login
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from django.views import View


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
            # Foydalanuvchini "next" parametri bo'yicha yoki bosh sahifaga yo'naltirish
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            # Xato xabari bilan login sahifasini qayta yuklash
            return render(request, 'auth/login.html', {'error': 'Invalid credentials'})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('/account/login/')
