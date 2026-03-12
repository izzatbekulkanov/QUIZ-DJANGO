from django.contrib import messages
from django.shortcuts import redirect, render

from question.models import SystemSetting


def site_settings_view(request):
    # Active setting (or None)
    setting = SystemSetting.objects.filter(is_active=True).first()

    if request.method == 'POST':
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

        if not name or not site_status:
            messages.error(request, "Tizim nomi va sayt holati maydonlari to'ldirilishi shart.")
            return render(request, 'question/views/site-settings.html', {'setting': setting})

        try:
            # Deactivate previous settings
            SystemSetting.objects.update(is_active=False)

            if not setting:
                setting = SystemSetting()

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
                setting.logo = logo
            if favicon:
                setting.favicon = favicon

            setting.save()
            messages.success(request, "Tizim sozlamalari muvaffaqiyatli saqlandi!")
            return redirect('site_settings')

        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
            return render(request, 'question/views/site-settings.html', {'setting': setting})

    return render(request, 'question/views/site-settings.html', {'setting': setting})