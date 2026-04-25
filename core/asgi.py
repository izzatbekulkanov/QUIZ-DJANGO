import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from core.startup import apply_runtime_patches

apply_runtime_patches()

from django.core.asgi import get_asgi_application

application = get_asgi_application()
