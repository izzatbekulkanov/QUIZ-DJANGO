# account/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, FaceEncoding
from django.contrib.auth.models import Group, Permission

class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'second_name', 'full_name', 'phone_number', 'address', 'date_of_birth', 'gender', 'profile_picture', 'nationality', 'bio')}),
        ('Additional info', {'fields': ('is_student', 'is_teacher', 'emergency_contact', 'job_title', 'company_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'second_name', 'full_name', 'phone_number', 'address', 'date_of_birth', 'gender', 'profile_picture', 'nationality', 'bio', 'is_student', 'is_teacher', 'emergency_contact', 'job_title', 'company_name', 'groups', 'user_permissions'),
        }),
    )

    list_display = ('username', 'email', 'full_name', 'phone_number', 'is_staff')
    search_fields = ('username', 'email', 'full_name', 'phone_number')
    ordering = ('username',)

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Permission)

@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    list_display = ('user', 'encoding_version', 'confidence_score', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['delete_selected']  # bulk delete uchun

    def delete_queryset(self, request, queryset):
        """Ommaviy o'chirish uchun optimallashtirilgan usul"""
        queryset.delete()