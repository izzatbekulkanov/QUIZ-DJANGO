from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission
from django.db.models import Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from apps.question.forms import RoleGroupManageForm


User = get_user_model()
ROLE_GROUP_SUPERADMIN_NAME = "Super Administrator"

APP_LABEL_DISPLAY = {
    "account": "Foydalanuvchilar",
    "admin": "Admin panel",
    "auth": "Autentifikatsiya",
    "contenttypes": "Tizim turlari",
    "logs": "Loglar",
    "question": "Test tizimi",
    "sessions": "Sessiyalar",
}

MODEL_DISPLAY = {
    "answer": "Javob varianti",
    "category": "Kategoriya",
    "customuser": "Foydalanuvchi",
    "group": "Guruh",
    "log": "Log yozuvi",
    "permission": "Ruxsat",
    "question": "Savol",
    "studenttest": "Natija",
    "studenttestassignment": "Topshiriq",
    "studenttestquestion": "Topshirilgan savol",
    "systemsetting": "Tizim sozlamasi",
    "test": "Test",
}

ACTION_DISPLAY = {
    "add": "Yaratish",
    "change": "Tahrirlash",
    "delete": "O'chirish",
    "view": "Ko'rish",
}

DEFAULT_ROLE_GROUP_BLUEPRINTS = (
    {
        "name": "Super Administrator",
        "description": "Tizimning barcha boshqaruv imkoniyatlari bilan to'liq rol.",
        "app_labels": None,
        "actions": None,
        "extra_q": Q(),
    },
    {
        "name": "System Administrator",
        "description": "Platforma, foydalanuvchi va test jarayonlarini kundalik boshqarish uchun kuchli rol.",
        "app_labels": {"account", "question", "logs"},
        "actions": None,
        "extra_q": Q(),
    },
    {
        "name": "Academic Operations Manager",
        "description": "O'quv jarayoni, testlar va natijalarni boshqaruvchi akademik bo'lim roli.",
        "app_labels": {"question"},
        "actions": None,
        "extra_q": Q(content_type__app_label="account", codename__startswith="view_"),
    },
    {
        "name": "Standard User",
        "description": "Faqat ko'rish va asosiy kuzatuv vazifalari uchun xavfsiz standart rol.",
        "app_labels": {"question"},
        "actions": {"view"},
        "extra_q": Q(content_type__app_label="account", codename__startswith="view_"),
    },
)


def _permission_queryset():
    return Permission.objects.select_related("content_type").order_by(
        "content_type__app_label",
        "content_type__model",
        "codename",
    )


def _can_manage_role_groups(user):
    if not getattr(user, "is_authenticated", False):
        return False

    return user.is_superuser or user.groups.filter(name=ROLE_GROUP_SUPERADMIN_NAME).exists()


def _user_queryset():
    return User.objects.only(
        "id",
        "username",
        "first_name",
        "second_name",
        "full_name",
        "is_student",
        "is_teacher",
        "is_staff",
        "is_superuser",
    ).order_by("second_name", "first_name", "username")


def _group_queryset():
    return Group.objects.order_by("name").prefetch_related(
        Prefetch("permissions", queryset=_permission_queryset()),
        Prefetch("user_set", queryset=_user_queryset()),
    )


def _titleize_identifier(value):
    return (value or "").replace("_", " ").strip().title()


def _display_model_name(model_name):
    return MODEL_DISPLAY.get(model_name, _titleize_identifier(model_name))


def _display_app_name(app_label):
    return APP_LABEL_DISPLAY.get(app_label, _titleize_identifier(app_label))


def _build_permission_uz_name(permission):
    codename = permission.codename or ""
    action, _, model_name = codename.partition("_")
    action_label = ACTION_DISPLAY.get(action)

    if action_label and model_name:
        return f"{action_label}: {_display_model_name(model_name)}"

    return permission.name or _titleize_identifier(codename)


def _decorate_permissions(permissions):
    decorated_permissions = []
    for permission in permissions:
        permission.uz_name = _build_permission_uz_name(permission)
        permission.app_label_uz = _display_app_name(permission.content_type.app_label)
        permission.model_label_uz = _display_model_name(permission.content_type.model)
        decorated_permissions.append(permission)
    return decorated_permissions


def _user_display_name(user):
    full_name = (getattr(user, "full_name", "") or "").strip()
    if full_name:
        return f"{user.username} - {full_name}"

    first_name = (getattr(user, "first_name", "") or "").strip()
    second_name = (getattr(user, "second_name", "") or "").strip()
    assembled_name = " ".join(part for part in [second_name, first_name] if part).strip()
    if assembled_name:
        return f"{user.username} - {assembled_name}"

    return user.username


def _build_permission_sections(permissions, selected_permission_ids=None):
    selected_permission_ids = selected_permission_ids or set()
    grouped_sections = OrderedDict()

    for permission in permissions:
        app_label = permission.content_type.app_label
        if app_label not in grouped_sections:
            grouped_sections[app_label] = {
                "app_label": app_label,
                "title": permission.app_label_uz,
                "permissions": [],
                "selected_count": 0,
            }

        grouped_sections[app_label]["permissions"].append(permission)
        if permission.id in selected_permission_ids:
            grouped_sections[app_label]["selected_count"] += 1

    return list(grouped_sections.values())


def _get_selected_id_set(form, field_name, fallback_ids=None):
    if form.is_bound:
        return {
            int(value)
            for value in form.data.getlist(field_name)
            if str(value).strip().isdigit()
        }

    return set(fallback_ids or [])


def _permission_filter_query(app_labels=None, actions=None, extra_q=None):
    query = Q()

    if app_labels:
        query |= Q(content_type__app_label__in=app_labels)

    if actions:
        for action in actions:
            query |= Q(codename__startswith=f"{action}_")

    if app_labels and actions:
        scoped_query = Q()
        for action in actions:
            scoped_query |= Q(
                content_type__app_label__in=app_labels,
                codename__startswith=f"{action}_",
            )
        query = scoped_query

    if extra_q is not None:
        query |= extra_q

    return query


def _resolve_default_role_permissions():
    permissions = _permission_queryset()
    role_permissions = []

    for blueprint in DEFAULT_ROLE_GROUP_BLUEPRINTS:
        if blueprint["app_labels"] is None and blueprint["actions"] is None:
            permission_ids = list(permissions.values_list("id", flat=True))
        else:
            query = _permission_filter_query(
                app_labels=blueprint["app_labels"],
                actions=blueprint["actions"],
                extra_q=blueprint["extra_q"],
            )
            permission_ids = list(
                permissions.filter(query).values_list("id", flat=True).distinct()
            )

        role_permissions.append(
            {
                "name": blueprint["name"],
                "description": blueprint["description"],
                "permission_ids": permission_ids,
            }
        )

    return role_permissions


def _collect_roles_overview(current_user):
    groups = list(_group_queryset())
    permissions = _decorate_permissions(list(_permission_queryset()))
    can_manage = _can_manage_role_groups(current_user)

    for group in groups:
        group.prefetched_permissions = _decorate_permissions(list(group.permissions.all()))
        group.prefetched_users = list(group.user_set.all())
        group.permission_total = len(group.prefetched_permissions)
        group.user_total = len(group.prefetched_users)
        group.detail_url = reverse("administrator:role-group-detail", args=[group.id])
        group.can_delete = can_manage

    return {
        "groups": groups,
        "permissions": permissions,
        "permission_sections": _build_permission_sections(permissions),
        "group_count": len(groups),
        "permission_count": len(permissions),
        "assigned_users_count": sum(group.user_total for group in groups),
        "groups_with_permissions_count": sum(1 for group in groups if group.permission_total),
        "available_users_count": User.objects.count(),
        "default_groups": _resolve_default_role_permissions(),
        "create_default_role_groups_url": reverse("administrator:create-default-role-groups"),
        "add_role_group_url": reverse("administrator:add-role-group"),
        "can_manage_role_groups": can_manage,
    }


def _build_group_context(form, permissions, current_user, role_group=None):
    selected_permission_ids = _get_selected_id_set(
        form,
        "permissions",
        fallback_ids=role_group.permissions.values_list("id", flat=True) if role_group else [],
    )
    selected_user_ids = _get_selected_id_set(
        form,
        "users",
        fallback_ids=role_group.user_set.values_list("id", flat=True) if role_group else [],
    )

    selected_permissions = [
        permission for permission in permissions if permission.id in selected_permission_ids
    ]
    selected_users = list(_user_queryset().filter(id__in=selected_user_ids))

    student_users_count = sum(1 for user in selected_users if getattr(user, "is_student", False))
    staff_users_count = len(selected_users) - student_users_count

    context = {
        "form": form,
        "permission_sections": _build_permission_sections(permissions, selected_permission_ids),
        "role_group": role_group,
        "role_group_permissions": selected_permissions,
        "role_group_users": selected_users,
        "selected_permission_ids": selected_permission_ids,
        "selected_users": selected_users,
        "current_permission_count": len(selected_permissions),
        "current_user_count": len(selected_users),
        "student_users_count": student_users_count,
        "staff_users_count": staff_users_count,
        "available_permissions_count": len(permissions),
        "available_users_count": _user_queryset().count(),
        "can_manage_role_groups": _can_manage_role_groups(current_user),
    }

    if role_group:
        context.update(
            {
                "page_title": role_group.name,
                "page_subtitle": "Guruh nomi, ruxsatlar va foydalanuvchi birikmalarini bir joydan boshqaring",
                "submit_label": "O'zgarishlarni saqlash",
                "back_url": reverse("administrator:roles"),
            }
        )
    else:
        context.update(
            {
                "page_title": "Yangi guruh",
                "page_subtitle": "Yangi rol guruhini yarating va unga kerakli ruxsatlarni biriktiring",
                "submit_label": "Guruhni yaratish",
                "back_url": reverse("administrator:roles"),
            }
        )

    return context


@method_decorator(login_required, name="dispatch")
class RolesView(View):
    template_name = "question/views/roles.html"

    def get(self, request):
        return render(request, self.template_name, _collect_roles_overview(request.user))


@method_decorator(login_required, name="dispatch")
class CreateDefaultRoleGroupsView(View):
    def post(self, request):
        if not _can_manage_role_groups(request.user):
            return HttpResponseForbidden("Bu amal uchun ruxsat yo'q.")

        created_names = []
        updated_names = []

        for blueprint in _resolve_default_role_permissions():
            role_group, created = Group.objects.get_or_create(name=blueprint["name"])
            role_group.permissions.set(blueprint["permission_ids"])
            if created:
                created_names.append(blueprint["name"])
            else:
                updated_names.append(blueprint["name"])

        message_parts = []
        if created_names:
            message_parts.append(f"Yaratildi: {', '.join(created_names)}")
        if updated_names:
            message_parts.append(f"Yangilandi: {', '.join(updated_names)}")

        messages.success(
            request,
            "Default guruhlar tayyorlandi. " + " | ".join(message_parts),
        )
        return redirect("administrator:roles")


@method_decorator(login_required, name="dispatch")
class RoleUserSearchView(View):
    def get(self, request):
        query = (request.GET.get("q") or "").strip()
        if not query:
            return JsonResponse({"results": []})

        users = list(
            _user_queryset().filter(
                Q(username__icontains=query)
                | Q(full_name__icontains=query)
                | Q(first_name__icontains=query)
                | Q(second_name__icontains=query)
            )[:20]
        )

        return JsonResponse(
            {
                "results": [
                    {
                        "id": user.id,
                        "text": _user_display_name(user),
                        "username": user.username,
                    }
                    for user in users
                ]
            }
        )


@method_decorator(login_required, name="dispatch")
class AddRoleGroupView(View):
    template_name = "question/views/role-group-form.html"

    def get(self, request):
        if not _can_manage_role_groups(request.user):
            return HttpResponseForbidden("Bu amal uchun ruxsat yo'q.")

        permissions = _decorate_permissions(list(_permission_queryset()))
        form = RoleGroupManageForm(
            permission_queryset=_permission_queryset(),
            include_users=False,
        )
        context = _build_group_context(form, permissions, request.user)
        return render(request, self.template_name, context)

    def post(self, request):
        if not _can_manage_role_groups(request.user):
            return HttpResponseForbidden("Bu amal uchun ruxsat yo'q.")

        permissions_qs = _permission_queryset()
        permissions = _decorate_permissions(list(permissions_qs))
        form = RoleGroupManageForm(
            request.POST,
            permission_queryset=permissions_qs,
            include_users=False,
        )

        if form.is_valid():
            role_group = Group.objects.create(name=form.cleaned_data["name"])
            role_group.permissions.set(form.cleaned_data["permissions"])
            messages.success(request, "Yangi guruh muvaffaqiyatli yaratildi.")
            return redirect("administrator:role-group-detail", group_id=role_group.pk)

        messages.error(
            request,
            "Guruhni yaratishda xatolik yuz berdi. Maydonlarni tekshirib qayta urinib ko'ring.",
        )
        return render(
            request,
            self.template_name,
            _build_group_context(form, permissions, request.user),
        )


@method_decorator(login_required, name="dispatch")
class RoleGroupDetailView(View):
    template_name = "question/views/role-group-form.html"

    def get_object(self, group_id):
        return get_object_or_404(_group_queryset(), pk=group_id)

    def get(self, request, group_id):
        role_group = self.get_object(group_id)
        permissions = _decorate_permissions(list(_permission_queryset()))
        form = RoleGroupManageForm(
            group_instance=role_group,
            permission_queryset=_permission_queryset(),
            user_queryset=_user_queryset(),
        )
        context = _build_group_context(form, permissions, request.user, role_group=role_group)
        return render(request, self.template_name, context)

    def post(self, request, group_id):
        if not _can_manage_role_groups(request.user):
            return HttpResponseForbidden("Bu amal uchun ruxsat yo'q.")

        role_group = self.get_object(group_id)
        permissions_qs = _permission_queryset()
        permissions = _decorate_permissions(list(permissions_qs))
        form = RoleGroupManageForm(
            request.POST,
            group_instance=role_group,
            permission_queryset=permissions_qs,
            user_queryset=_user_queryset(),
        )

        if form.is_valid():
            role_group.name = form.cleaned_data["name"]
            role_group.save(update_fields=["name"])
            role_group.permissions.set(form.cleaned_data["permissions"])
            role_group.user_set.set(form.cleaned_data["users"])
            messages.success(request, "Guruh ma'lumotlari yangilandi.")
            return redirect("administrator:role-group-detail", group_id=role_group.pk)

        messages.error(
            request,
            "Guruh ma'lumotlarini saqlab bo'lmadi. Kiritilgan qiymatlarni tekshiring.",
        )
        return render(
            request,
            self.template_name,
            _build_group_context(form, permissions, request.user, role_group=role_group),
        )


@method_decorator(login_required, name="dispatch")
class DeleteRoleGroupView(View):
    def post(self, request, group_id):
        if not _can_manage_role_groups(request.user):
            return HttpResponseForbidden("Bu amal uchun ruxsat yo'q.")

        role_group = get_object_or_404(Group, pk=group_id)
        group_name = role_group.name
        role_group.delete()
        messages.success(request, f"'{group_name}' guruhi o'chirildi.")
        return redirect("administrator:roles")
