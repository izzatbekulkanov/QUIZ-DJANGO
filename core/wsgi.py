"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

from core.startup import apply_runtime_patches

apply_runtime_patches()

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
