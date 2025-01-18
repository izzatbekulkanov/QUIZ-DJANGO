from logs.models import Log
from django.utils.timezone import now, timedelta

def clear_old_logs():
    thirty_days_ago = now() - timedelta(days=30)
    deleted, _ = Log.objects.filter(timestamp__lt=thirty_days_ago).delete()
    print(f'{deleted} old logs have been cleared.')