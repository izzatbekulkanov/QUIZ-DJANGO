import logging

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError

from .models import Log


User = get_user_model()
logger = logging.getLogger(__name__)

class LogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        request_path = request.get_full_path()

        if request.path.rstrip("/").endswith("/logs/clear"):
            return response

        # Log data
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        user = request.user if request.user.is_authenticated else None

        # Logni saqlash
        try:
            log = Log.objects.create(
                ip_address=ip_address,
                method=request.method,
                path=request_path,
                status_code=response.status_code,
                user_agent=user_agent,
                user=user,
            )
            logger.debug(
                "Log yozildi: %s %s (%s) - Foydalanuvchi: %s",
                log.method,
                log.path,
                log.status_code,
                log.user.username if log.user else "Anonim",
            )
        except IntegrityError as e:
            logger.warning("Log yozishda xato: %s - Path: %s", str(e), request_path)

        return response

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @staticmethod
    def print_log(log):
        """Log ma'lumotlarini terminalga chiqarish"""
        logger.debug(
            "Vaqt: %s | IP: %s | Metod: %s | Path: %s | Status: %s | User Agent: %s | Foydalanuvchi: %s",
            log.timestamp,
            log.ip_address,
            log.method,
            log.path,
            log.status_code,
            log.user_agent,
            log.user.username if log.user else "Anonim",
        )
