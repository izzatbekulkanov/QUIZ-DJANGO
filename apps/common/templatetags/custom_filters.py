import json

from django import template
from django.utils.safestring import mark_safe

from apps.question.models import Answer
from apps.question.utils.utils import clean_import_answer_fragment, clean_import_question_fragment

register = template.Library()

@register.filter
def get_answer(answer_id):
    """
    Javob ID'si bo'yicha Answer obyektini qaytaradi.
    """
    try:
        return Answer.objects.get(id=answer_id)
    except Answer.DoesNotExist:
        return None

@register.filter
def to_json(value):
    return json.dumps(value, ensure_ascii=False)


@register.filter
def clean_import_question(value):
    return mark_safe(clean_import_question_fragment(value))


@register.filter
def clean_import_answer(value):
    return mark_safe(clean_import_answer_fragment(value))
