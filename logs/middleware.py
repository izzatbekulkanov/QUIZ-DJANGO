from .models import Log
from django.utils.timezone import now
from django.contrib.auth import get_user_model

User = get_user_model()

class LogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log data
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        user = request.user if request.user.is_authenticated else None

        # Logni saqlash
        log = Log.objects.create(
            timestamp=now(),
            ip_address=ip_address,
            method=request.method,
            path=request.get_full_path(),
            status_code=response.status_code,
            user_agent=user_agent,
            user=user,
        )

        # Terminalga chiqarish
        # self.print_log(log)

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
        print(f"""
       
        Vaqt: {log.timestamp}
        IP Manzil: {log.ip_address}
        Metod: {log.method}
        Path: {log.path}
        Status Code: {log.status_code}
        User Agent: {log.user_agent}
        Foydalanuvchi: {log.user.username if log.user else "Anonim"}
        """)
