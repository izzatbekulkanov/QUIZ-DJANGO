import json

from django import template

from question.models import Answer

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