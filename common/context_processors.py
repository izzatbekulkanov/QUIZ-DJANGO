from question.models import SystemSetting

def system_settings(request):
    setting = SystemSetting.objects.filter(is_active=True).first()
    return {
        'system': setting
    }
