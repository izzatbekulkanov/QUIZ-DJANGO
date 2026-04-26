# account/urls.py
from django.urls import path
from .views import LoginView, LogoutView, RegisterView, check_username, TwoLoginView, IdLoginView, OfficeHelperSessionStateView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('login/two-step/', TwoLoginView.as_view(), name='two_login'),
    path('login/id/', IdLoginView.as_view(), name='id_login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('office-helper/session-state/', OfficeHelperSessionStateView.as_view(), name='office-helper-session-state'),
    path('register/', RegisterView.as_view(), name='register'),
    path('check-username/', check_username, name='check-username'),
]
