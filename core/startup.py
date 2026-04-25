def apply_runtime_patches():
    from apps.common.compat import apply_django_context_copy_patch

    apply_django_context_copy_patch()
