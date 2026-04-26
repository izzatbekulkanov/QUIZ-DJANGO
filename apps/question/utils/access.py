from __future__ import annotations

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.question.models import StudentTestAssignment


ASSIGNMENT_ACCESS_SALT = "question.assignment.access"
ASSIGNMENT_ACCESS_MAX_AGE = 60 * 60 * 24 * 30


def build_assignment_access_token(user_id: int, assignment_id: int) -> str:
    return signing.dumps(
        {"user_id": int(user_id), "assignment_id": int(assignment_id)},
        salt=ASSIGNMENT_ACCESS_SALT,
        compress=True,
    )


def user_can_access_assignment(user, assignment: StudentTestAssignment) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if assignment.teacher_id == user.id:
        return True
    if assignment.test.created_by_id == user.id:
        return True
    return assignment.test.students.filter(id=user.id).exists()


def build_assignment_access_urls(user, assignment: StudentTestAssignment) -> dict[str, str]:
    from django.urls import reverse

    token = build_assignment_access_token(user.id, assignment.id)
    return {
        "token": token,
        "instructions_url": reverse("landing:start-test-detail", args=[token]),
        "start_url": reverse("landing:start-test", args=[token]),
        "unfinished_status_url": reverse("landing:check-unfinished-test", args=[token]),
    }


def resolve_assignment_access(request_user, assignment_token: str) -> tuple[StudentTestAssignment, str, bool]:
    assignment = None
    is_legacy = False

    if assignment_token.isdigit():
        assignment = get_object_or_404(
            StudentTestAssignment.objects.select_related("test", "teacher", "category", "test__created_by"),
            id=int(assignment_token),
        )
        is_legacy = True
    else:
        try:
            payload = signing.loads(
                assignment_token,
                salt=ASSIGNMENT_ACCESS_SALT,
                max_age=ASSIGNMENT_ACCESS_MAX_AGE,
            )
        except signing.BadSignature as exc:
            raise Http404("Test havolasi yaroqsiz yoki eskirgan.") from exc

        if int(payload.get("user_id") or 0) != request_user.id:
            raise PermissionDenied("Bu test havolasi boshqa foydalanuvchiga tegishli.")

        assignment = get_object_or_404(
            StudentTestAssignment.objects.select_related("test", "teacher", "category", "test__created_by"),
            id=int(payload.get("assignment_id") or 0),
        )

    if not user_can_access_assignment(request_user, assignment):
        raise PermissionDenied("Bu topshiriqni ochish uchun ruxsat yo'q.")

    return assignment, build_assignment_access_token(request_user.id, assignment.id), is_legacy
