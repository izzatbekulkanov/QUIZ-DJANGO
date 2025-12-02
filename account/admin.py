# account/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, FaceEncoding
from django.contrib.auth.models import Group, Permission
from django.utils.html import format_html
import pickle
import numpy as np  # Encodingni o'qish uchun zarur
from django.urls import reverse

class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {
            'fields': ('first_name', 'second_name', 'full_name', 'phone_number', 'address', 'date_of_birth', 'gender',
                       'profile_picture', 'nationality', 'bio')}),
        ('Additional info', {'fields': ('is_student', 'is_teacher', 'emergency_contact', 'job_title', 'company_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'second_name', 'full_name', 'phone_number',
                       'address', 'date_of_birth', 'gender', 'profile_picture', 'nationality', 'bio', 'is_student',
                       'is_teacher', 'emergency_contact', 'job_title', 'company_name', 'groups', 'user_permissions'),
        }),
    )

    list_display = ('username', 'email', 'full_name', 'phone_number', 'is_staff')
    search_fields = ('username', 'email', 'full_name', 'phone_number')
    ordering = ('username',)


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Permission)


# Agar model boshqa faylda bo'lsa, import qiling: from .models import FaceEncoding

@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    # 1. Ro'yxat ko'rinishi (List Display)
    # Bu yerdagi ustunlar ro'yxatda ko'rinadi.
    list_display = (
        'id',
        'user',  # CustomUser ga bog'lanish linki
        'encoding_version',
        'confidence_score',
        'image_resolution',
        'created_at',
    )

    # 2. Ro'yxatdagi qatorni tahrirlash uchun link yaratuvchi ustun.
    # Bu yerda faqat 'id' ni belgilaymiz, shunda butun qator CustomUserga o'tib ketmaydi.
    list_display_links = ('id',)

    # 3. Filtrlash va Qidiruv
    list_filter = ('encoding_version', 'created_at')
    search_fields = ('user__username', 'encoding_version')

    # 4. Faqat o'qish uchun maydonlar
    # BinaryField maydonlari va vaqt tamg'alari faqat ko'rish uchun chiqariladi.
    readonly_fields = (
        'encoding',  # <-- Encoding maydoni
        'facial_features',  # <-- Facial Features maydoni
        'created_at',
        'updated_at',
    )

    # 5. Formani joylashtirish (Fieldsets for Change View)
    # Tahrirlash sahifasida maydonlarni chiqarish uchun majburiy.
    fieldsets = (
        ('Asosiy Ma\'lumot', {
            'fields': ('user', 'image_resolution', 'encoding_version', 'confidence_score')
        }),
        ('Kodlash Ma\'lumotlari', {
            # Bu yerdagi maydonlar endi readonly_fields'ga kiritilgani uchun xato bermasligi kerak.
            'fields': ('encoding', 'facial_features'),
            'description': 'Yuz kodlari ikkilik formatda saqlanadi va tahrirlanmaydi.',
        }),
        ('Vaqt Tamg\'alari', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    # 6. Actionlar
    actions = ['delete_selected']

    def delete_queryset(self, request, queryset):
        """Ommaviy o'chirish uchun standart usul"""
        deleted_count, _ = queryset.delete()
        self.message_user(
            request,
            f"Muvaffaqiyatli o'chirildi: {deleted_count} ta yuz kodi o'chirildi."
        )