# logs/models.py
from django.db import models
from django.utils.timezone import now

from core import settings


class Log(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    method = models.CharField(max_length=10)
    path = models.TextField()
    status_code = models.IntegerField()
    user_agent = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Foydalanuvchi modeli bilan dinamik bog‘lanish
        null=True, blank=True, on_delete=models.SET_NULL, related_name='logs'
    )

    def __str__(self):
        return f"[{self.timestamp}] {self.method} {self.path} ({self.status_code})"