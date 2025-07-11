from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from question.models import SystemSetting


def site_settings_view(request):
    print("🔧 Tizim sozlamalari sahifasiga so‘rov keldi:", request.method)

    # Faol sozlamani olish, agar yo‘q bo‘lsa None
    setting = SystemSetting.objects.filter(is_active=True).first()

    if request.method == 'POST':
        print("📥 POST so‘rovi qabul qilindi")

        # Ma'lumotlarni olish
        name = request.POST.get('name', '')
        description = request.POST.get('description', '')
        contact_email = request.POST.get('contact_email', '')
        contact_phone = request.POST.get('contact_phone', '')
        address = request.POST.get('address', '')
        footer_text = request.POST.get('footer_text', '')
        hemis_url = request.POST.get('hemis_url', '')
        hemis_api_key = request.POST.get('hemis_api_key', '')
        site_status = request.POST.get('site_status', '')
        status_message = request.POST.get('status_message', '')
        logo = request.FILES.get('logo')
        favicon = request.FILES.get('favicon')

        # Majburiy maydonlarni tekshirish
        if not name or not site_status:
            print("⚠️ Majburiy maydonlar to‘ldirilmagan")
            messages.error(request, "❌ Tizim nomi va sayt holati maydonlari to‘ldirilishi shart.")
            return render(request, 'question/views/site-settings.html', {
                'setting': setting
            })

        try:
            # Avvalgi sozlamalarni nofaol qilish
            SystemSetting.objects.update(is_active=False)

            # Mavjud sozlamani yangilash yoki yangi yaratish
            if setting:
                print("🔁 Mavjud sozlama yangilanmoqda")
            else:
                print("🆕 Yangi sozlama yaratilmoqda")
                setting = SystemSetting()

            # Ma'lumotlarni saqlash
            setting.name = name
            setting.description = description
            setting.contact_email = contact_email
            setting.contact_phone = contact_phone
            setting.address = address
            setting.footer_text = footer_text
            setting.hemis_url = hemis_url
            setting.hemis_api_key = hemis_api_key
            setting.status = site_status
            setting.status_message = status_message
            setting.is_active = True

            if logo:
                print("📤 Logo yangilanmoqda")
                setting.logo = logo
            if favicon:
                print("📤 Favicon yangilanmoqda")
                setting.favicon = favicon

            setting.save()
            print(f"✅ Sozlamalar saqlandi: {setting.name}")
            messages.success(request, "✅ Tizim sozlamalari muvaffaqiyatli saqlandi!")
            return redirect('site_settings')

        except Exception as e:
            print(f"❌ Xatolik yuz berdi: {e}")
            messages.error(request, f"❌ Xatolik: {str(e)}")
            return render(request, 'question/views/site-settings.html', {
                'setting': setting
            })

    # GET so‘rovi uchun
    return render(request, 'question/views/site-settings.html', {
        'setting': setting
    })