from django.urls import path
from .views import LogsView, ClearLogsView

urlpatterns = [
    path('', LogsView.as_view(), name='logs'),
    path('clear/', ClearLogsView.as_view(), name='clear-logs'),  # Loglarni tozalash uchun
]
