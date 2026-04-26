from __future__ import annotations

from threading import Lock

from django.db import connection
from django.db.utils import OperationalError, ProgrammingError


_schema_lock = Lock()
_student_test_question_schema_ready = False
_help_result_plan_schema_ready = False


def ensure_student_test_question_proctoring_schema() -> bool:
    global _student_test_question_schema_ready

    if _student_test_question_schema_ready:
        return True

    from apps.question.models import StudentTestQuestion

    with _schema_lock:
        if _student_test_question_schema_ready:
            return True

        table_name = StudentTestQuestion._meta.db_table
        try:
            table_names = set(connection.introspection.table_names())
            if table_name not in table_names:
                return False

            with connection.cursor() as cursor:
                columns = {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, table_name)
                }

            missing_fields = []
            for field_name in ("answered_at", "answer_snapshot"):
                field = StudentTestQuestion._meta.get_field(field_name)
                if field.column not in columns:
                    missing_fields.append(field)

            if not missing_fields:
                _student_test_question_schema_ready = True
                return True

            with connection.schema_editor() as schema_editor:
                for field in missing_fields:
                    schema_editor.add_field(StudentTestQuestion, field)

            _student_test_question_schema_ready = True
            return True
        except (OperationalError, ProgrammingError):
            return False


def ensure_help_result_plan_schema() -> bool:
    global _help_result_plan_schema_ready

    if _help_result_plan_schema_ready:
        return True

    from apps.question.models import HelpResultPlan

    with _schema_lock:
        if _help_result_plan_schema_ready:
            return True

        table_name = HelpResultPlan._meta.db_table
        try:
            table_names = set(connection.introspection.table_names())
            if table_name not in table_names:
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(HelpResultPlan)
                _help_result_plan_schema_ready = True
                return True

            with connection.cursor() as cursor:
                columns = {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, table_name)
                }

            missing_fields = []
            for field in HelpResultPlan._meta.local_fields:
                if field.column not in columns:
                    missing_fields.append(field)

            if missing_fields:
                with connection.schema_editor() as schema_editor:
                    for field in missing_fields:
                        schema_editor.add_field(HelpResultPlan, field)

            _help_result_plan_schema_ready = True
            return True
        except (OperationalError, ProgrammingError):
            return False
