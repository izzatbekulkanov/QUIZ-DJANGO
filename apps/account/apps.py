from django.apps import AppConfig
from django.db.backends.signals import connection_created


class AccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.account'

    def ready(self):
        from apps.account.schema import ensure_custom_user_help_schema

        connection_created.connect(
            ensure_custom_user_help_schema,
            dispatch_uid="apps.account.ensure_custom_user_help_schema",
        )
