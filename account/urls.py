# account/urls.py
from django.urls import path
from .views import LoginView, LogoutView, RegisterView, check_username, FaceLoginView, TwoLoginView, IdLoginView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('face-login/', FaceLoginView.as_view(), name='face_login'),
    path('two-login/', TwoLoginView.as_view(), name='two_login'),
    path('id-login/', IdLoginView.as_view(), name='id_login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('check-username/', check_username, name='check-username'),
]
