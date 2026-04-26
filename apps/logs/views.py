from datetime import datetime, time, timedelta
from hashlib import md5

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views import View

from apps.logs.models import Log


LOGS_CACHE_VERSION_KEY = "administrator_logs_cache_version"
LOGS_STATS_CACHE_TTL = 60
LOGS_FILTER_COUNT_CACHE_TTL = 45


class PreCountPaginator(Paginator):
    def __init__(self, *args, count_value=None, **kwargs):
        self._count_value = count_value
        super().__init__(*args, **kwargs)

    @cached_property
    def count(self):
        if self._count_value is not None:
            return self._count_value
        return super().count


def _get_logs_cache_version():
    version = cache.get(LOGS_CACHE_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(LOGS_CACHE_VERSION_KEY, version, None)
    return version


def _make_logs_cache_key(prefix, suffix=""):
    return f"administrator_logs:{_get_logs_cache_version()}:{prefix}:{suffix}"


@method_decorator(login_required, name='dispatch')
class LogsView(View):
    template_name = 'logs/views/logs.html'
    page_size = 50

    def _get_global_stats(self):
        cache_key = _make_logs_cache_key("stats")
        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            return cached_stats

        today = timezone.localdate()
        start_of_today = timezone.make_aware(datetime.combine(today, time.min))
        end_of_today = start_of_today + timedelta(days=1)

        stats = Log.objects.aggregate(
            total_logs_count=Count("id"),
            today_logs_count=Count(
                "id",
                filter=Q(timestamp__gte=start_of_today, timestamp__lt=end_of_today),
            ),
            error_logs_count=Count("id", filter=Q(status_code__gte=400)),
            unique_users_count=Count("user", distinct=True, filter=Q(user__isnull=False)),
        )
        cache.set(cache_key, stats, LOGS_STATS_CACHE_TTL)
        return stats

    def _get_filtered_count(self, queryset, filters):
        if not any(filters.values()):
            return self._get_global_stats()["total_logs_count"]

        serialized = "&".join(
            f"{key}={value}" for key, value in sorted(filters.items()) if value
        )
        digest = md5(serialized.encode("utf-8")).hexdigest()
        cache_key = _make_logs_cache_key("filtered-count", digest)
        cached_count = cache.get(cache_key)
        if cached_count is not None:
            return cached_count

        filtered_count = queryset.count()
        cache.set(cache_key, filtered_count, LOGS_FILTER_COUNT_CACHE_TTL)
        return filtered_count

    def get(self, request):
        logs_queryset = (
            Log.objects.select_related("user")
            .only("id", "timestamp", "ip_address", "method", "path", "status_code", "user__username")
            .order_by("-id")
        )

        # Filtrlar
        user_filter = (request.GET.get('user') or '').strip()
        ip_filter = (request.GET.get('ip') or '').strip()
        method_filter = (request.GET.get('method') or '').strip().upper()
        path_filter = (request.GET.get('path') or '').strip()
        date_filter = (request.GET.get('date') or '').strip()

        if user_filter:
            logs_queryset = logs_queryset.filter(user__username__icontains=user_filter)
        if ip_filter:
            logs_queryset = logs_queryset.filter(ip_address__icontains=ip_filter)
        if method_filter:
            logs_queryset = logs_queryset.filter(method=method_filter)
        if path_filter:
            logs_queryset = logs_queryset.filter(path__icontains=path_filter)
        if date_filter:
            parsed_date = parse_date(date_filter)
            if parsed_date:
                start_of_day = timezone.make_aware(datetime.combine(parsed_date, time.min))
                end_of_day = start_of_day + timedelta(days=1)
                logs_queryset = logs_queryset.filter(timestamp__gte=start_of_day, timestamp__lt=end_of_day)
            else:
                date_filter = ''

        filters = {
            'user': user_filter,
            'ip': ip_filter,
            'method': method_filter,
            'path': path_filter,
            'date': date_filter,
        }
        filtered_logs_count = self._get_filtered_count(logs_queryset, filters)
        paginator = PreCountPaginator(logs_queryset, self.page_size, count_value=filtered_logs_count)
        page_number = request.GET.get('page')
        logs = paginator.get_page(page_number)
        query_params = request.GET.copy()
        query_params.pop('page', None)

        global_stats = self._get_global_stats()

        context = {
            'logs': logs,
            'total_logs_count': global_stats["total_logs_count"],
            'filtered_logs_count': filtered_logs_count,
            'today_logs_count': global_stats["today_logs_count"],
            'error_logs_count': global_stats["error_logs_count"],
            'unique_users_count': global_stats["unique_users_count"],
            'pagination_query': query_params.urlencode(),
            'filters': filters,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class ClearLogsView(View):
    def post(self, request):
        if request.user.is_superuser:  # Faqat admin foydalanuvchilar uchun ruxsat
            try:
                Log.objects.all().delete()  # Barcha loglarni o'chirish
                cache.set(LOGS_CACHE_VERSION_KEY, _get_logs_cache_version() + 1, None)
                return JsonResponse({"success": True, "message": "Barcha loglar muvaffaqiyatli o'chirildi!"})
            except Exception as e:
                return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"})
        else:
            return JsonResponse({"success": False, "message": "Sizda bu amalni bajarish uchun ruxsat yo'q!"})
