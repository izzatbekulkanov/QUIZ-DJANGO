from __future__ import annotations

from threading import Lock

from django.db import connection as default_connection
from django.db.utils import OperationalError, ProgrammingError


_schema_lock = Lock()
_custom_user_help_schema_ready = False


def ensure_custom_user_help_schema(sender=None, connection=None, **kwargs) -> bool:
    global _custom_user_help_schema_ready

    if _custom_user_help_schema_ready:
        return True

    from apps.account.models import CustomUser
    db_connection = connection or default_connection

    with _schema_lock:
        if _custom_user_help_schema_ready:
            return True

        table_name = CustomUser._meta.db_table
        try:
            table_names = set(db_connection.introspection.table_names())
            if table_name not in table_names:
                return False

            with db_connection.cursor() as cursor:
                columns = {
                    column.name
                    for column in db_connection.introspection.get_table_description(cursor, table_name)
                }

            field = CustomUser._meta.get_field("is_help")
            if field.column in columns:
                _custom_user_help_schema_ready = True
                return True

            with db_connection.schema_editor() as schema_editor:
                schema_editor.add_field(CustomUser, field)

            _custom_user_help_schema_ready = True
            return True
        except (OperationalError, ProgrammingError):
            return False
