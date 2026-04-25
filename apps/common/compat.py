import sys
from copy import copy

import django


def apply_django_context_copy_patch():
    """
    Work around Django 5.1 on Python 3.14 copying template contexts via
    ``copy(super())``, which raises during admin template rendering.
    """
    if sys.version_info < (3, 14):
        return

    try:
        major, minor, *_ = django.VERSION
    except Exception:
        return

    if (major, minor) != (5, 1):
        return

    from django.template.context import BaseContext, Context

    if getattr(BaseContext.__copy__, "_quiz_patch_applied", False):
        return

    def _base_context_copy(self):
        duplicate = object.__new__(self.__class__)
        if hasattr(self, "__dict__"):
            duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    def _context_copy(self):
        duplicate = BaseContext.__copy__(self)
        duplicate.render_context = copy(self.render_context)
        return duplicate

    _base_context_copy._quiz_patch_applied = True
    _context_copy._quiz_patch_applied = True

    BaseContext.__copy__ = _base_context_copy
    Context.__copy__ = _context_copy
