# logs/admin.py
from django.contrib import admin
from .models import Log


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'method', 'path', 'status_code', 'ip_address', 'user')  # Admin panelda ko‘rinadigan ustunlar
    list_filter = ('method', 'status_code', 'user')  # Filtrlash imkoniyatlari
    search_fields = ('path', 'ip_address', 'user__username')  # Qidiruv maydonlari
    date_hierarchy = 'timestamp'  # Sana bo‘yicha ko‘rinish
    ordering = ('-timestamp',)  # Eng yangi loglar yuqorida
    readonly_fields = ('timestamp', 'ip_address', 'method', 'path', 'status_code', 'user_agent', 'user')  # Faqat o‘qish uchun maydonlar

    def has_add_permission(self, request):
        """Log yozuvlarini qo‘lda qo‘shishga ruxsat bermaslik."""
        return False

    def has_change_permission(self, request, obj=None):
        """Log yozuvlarini o‘zgartirishga ruxsat bermaslik."""
        return False