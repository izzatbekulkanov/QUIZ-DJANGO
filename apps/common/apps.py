from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'

    def ready(self):
        from .compat import apply_django_context_copy_patch

        apply_django_context_copy_patch()
