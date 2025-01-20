from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from logs.models import Log


# Create your views here.
@method_decorator(login_required, name='dispatch')
class LogsView(View):
    template_name = 'logs/views/logs.html'

    def get(self, request):
        logs_queryset = Log.objects.all().order_by('-timestamp')  # Loglarni tartiblash

        # Filtrlar
        user_filter = request.GET.get('user', None)
        ip_filter = request.GET.get('ip', None)
        method_filter = request.GET.get('method', None)
        path_filter = request.GET.get('path', None)
        date_filter = request.GET.get('date', None)

        if user_filter:
            logs_queryset = logs_queryset.filter(user__username__icontains=user_filter)
        if ip_filter:
            logs_queryset = logs_queryset.filter(ip_address__icontains=ip_filter)
        if method_filter:
            logs_queryset = logs_queryset.filter(method__icontains=method_filter)
        if path_filter:
            logs_queryset = logs_queryset.filter(path__icontains=path_filter)
        if date_filter:
            logs_queryset = logs_queryset.filter(timestamp__date=date_filter)

        paginator = Paginator(logs_queryset, 50)  # Har bir sahifada 50 log
        page_number = request.GET.get('page')  # Hozirgi sahifa raqamini olish
        logs = paginator.get_page(page_number)  # Hozirgi sahifadagi loglar

        context = {
            'logs': logs,  # Loglar obyekti
            'filters': {
                'user': user_filter,
                'ip': ip_filter,
                'method': method_filter,
                'path': path_filter,
                'date': date_filter,
            },  # Qidiruv filtrlari
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class ClearLogsView(View):
    def post(self, request):
        if request.user.is_superuser:  # Faqat admin foydalanuvchilar uchun ruxsat
            try:
                Log.objects.all().delete()  # Barcha loglarni o'chirish
                return JsonResponse({"success": True, "message": "Barcha loglar muvaffaqiyatli o'chirildi!"})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"})
        else:
            return JsonResponse({"success": False, "message": "Sizda bu amalni bajarish uchun ruxsat yo'q!"})