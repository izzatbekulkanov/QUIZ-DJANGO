from __future__ import annotations

from dataclasses import dataclass

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.account.models import CustomUser
from apps.logs.models import Log
from apps.question.models import HelpResultPlan, StudentTest, StudentTestAssignment
from apps.question.utils.schema import ensure_help_result_plan_schema
from core.error_views import render_error_page


HELP_GROUP_ALL = "__all__"
HELP_GROUP_UNGROUPED = "__ungrouped__"


def user_can_access_help_menu(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_help", False)
    )


class HelpAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        if not user_can_access_help_menu(request.user):
            return render_error_page(request, status_code=404)
        return super().dispatch(request, *args, **kwargs)


class HelpUsersView(HelpAccessMixin, View):
    template_name = "question/views/help-users.html"
    page_size = 30
    list_fields = (
        "id",
        "username",
        "first_name",
        "second_name",
        "full_name",
        "group_name",
        "is_student",
        "is_teacher",
        "is_help",
        "profile_picture",
    )

    def _base_queryset(self):
        return (
            CustomUser.objects.only(*self.list_fields)
            .annotate(
                assigned_tests_count=Count("assigned_tests", distinct=True),
                student_results_count=Count("student_tests", distinct=True),
            )
        )

    def _group_options(self):
        return list(
            CustomUser.objects.exclude(group_name__isnull=True)
            .exclude(group_name__exact="")
            .values_list("group_name", flat=True)
            .distinct()
            .order_by("group_name")
        )

    def get(self, request):
        search_query = (request.GET.get("search") or "").strip()
        group_name = (request.GET.get("group_name") or HELP_GROUP_UNGROUPED).strip() or HELP_GROUP_UNGROUPED

        users_queryset = self._base_queryset()

        if search_query:
            users_queryset = users_queryset.filter(
                Q(full_name__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(second_name__icontains=search_query)
                | Q(username__icontains=search_query)
            )

        if group_name == HELP_GROUP_UNGROUPED:
            users_queryset = users_queryset.filter(Q(group_name__isnull=True) | Q(group_name__exact=""))
        elif group_name != HELP_GROUP_ALL:
            users_queryset = users_queryset.filter(group_name=group_name)

        users_queryset = users_queryset.order_by("group_name", "second_name", "first_name", "username")

        paginator = Paginator(users_queryset, self.page_size)
        users = paginator.get_page(request.GET.get("page"))

        query_params = request.GET.copy()
        query_params.pop("page", None)

        context = {
            "users": users,
            "search_query": search_query,
            "group_name": group_name,
            "group_options": self._group_options(),
            "pagination_query": query_params.urlencode(),
            "total_users_count": CustomUser.objects.count(),
            "filtered_users_count": paginator.count,
            "ungrouped_users_count": CustomUser.objects.filter(Q(group_name__isnull=True) | Q(group_name__exact="")).count(),
            "help_enabled_count": CustomUser.objects.filter(is_help=True).count(),
        }
        return render(request, self.template_name, context)


class HelpPlansView(HelpAccessMixin, View):
    template_name = "question/views/help-plans.html"
    page_size = 50

    def get(self, request):
        ensure_help_result_plan_schema()

        search_query = (request.GET.get("search") or "").strip()
        status = (request.GET.get("status") or "").strip()

        plans_queryset = (
            HelpResultPlan.objects.select_related(
                "student",
                "test",
                "assignment__category",
                "assignment__teacher",
                "created_by",
            )
            .order_by("-created_at", "-id")
        )

        if search_query:
            plans_queryset = plans_queryset.filter(
                Q(student__username__icontains=search_query)
                | Q(student__full_name__icontains=search_query)
                | Q(student__first_name__icontains=search_query)
                | Q(student__second_name__icontains=search_query)
                | Q(test__name__icontains=search_query)
                | Q(assignment__category__name__icontains=search_query)
                | Q(created_by__username__icontains=search_query)
                | Q(created_by__full_name__icontains=search_query)
            )

        if status in dict(HelpResultPlan.STATUS_CHOICES):
            plans_queryset = plans_queryset.filter(status=status)
        else:
            status = ""

        paginator = Paginator(plans_queryset, self.page_size)
        plans = paginator.get_page(request.GET.get("page"))
        plan_items = list(plans.object_list)

        latest_attempt_map = _build_latest_attempt_map(plan_items)
        for plan in plan_items:
            plan.latest_attempt_summary = (
                latest_attempt_map.get((plan.student_id, plan.assignment_id))
                if plan.status == HelpResultPlan.STATUS_COMPLETED
                else None
            )
            plan.detail_url = reverse(
                "administrator:help-assignment-detail",
                args=[plan.student_id, plan.assignment_id],
            )
            plan.delete_url = reverse("administrator:delete-help-plan", args=[plan.id])

        query_params = request.GET.copy()
        query_params.pop("page", None)

        base_queryset = HelpResultPlan.objects.all()
        context = {
            "plans": plans,
            "plan_items": plan_items,
            "search_query": search_query,
            "selected_status": status,
            "status_choices": HelpResultPlan.STATUS_CHOICES,
            "pagination_query": query_params.urlencode(),
            "delete_all_url": reverse("administrator:delete-all-help-plans"),
            "stats": {
                "total_count": base_queryset.count(),
                "pending_count": base_queryset.filter(status=HelpResultPlan.STATUS_PENDING).count(),
                "completed_count": base_queryset.filter(status=HelpResultPlan.STATUS_COMPLETED).count(),
                "filtered_count": paginator.count,
            },
        }
        return render(request, self.template_name, context)


class DeleteHelpPlanView(HelpAccessMixin, View):
    def post(self, request, plan_id):
        ensure_help_result_plan_schema()
        request.skip_request_log = True
        redirect_url = reverse("administrator:help-plans")

        with transaction.atomic():
            plan = get_object_or_404(
                HelpResultPlan.objects.select_for_update().select_related("student", "assignment__test"),
                id=plan_id,
            )

            if plan.status == HelpResultPlan.STATUS_PENDING:
                confirmation = (request.POST.get("confirmation") or "").strip()
                if confirmation != "DELETE":
                    messages.error(request, "Kutilayotgan yordam qaydini o'chirish uchun DELETE deb yozish kerak.")
                    return redirect(redirect_url)

            plan_label = f"{plan.student} - {plan.assignment.test.name}"
            _delete_help_plan_logs(plan)
            plan.delete()

        messages.success(request, f"Yordam qaydi o'chirildi: {plan_label}.")
        return redirect(redirect_url)


class DeleteAllHelpPlansView(HelpAccessMixin, View):
    def post(self, request):
        ensure_help_result_plan_schema()
        request.skip_request_log = True
        redirect_url = reverse("administrator:help-plans")
        confirmation = (request.POST.get("confirmation") or "").strip()

        if confirmation != "DELETE":
            messages.error(request, "Barcha yordam qaydlarini o'chirish uchun DELETE deb yozish kerak.")
            return redirect(redirect_url)

        with transaction.atomic():
            plans_count = HelpResultPlan.objects.count()
            HelpResultPlan.objects.all().delete()
            logs_count = _delete_all_help_logs()

        messages.success(
            request,
            f"{plans_count} ta yordam qaydi va {logs_count} ta help log yozuvi o'chirildi.",
        )
        return redirect(redirect_url)


@dataclass
class AssignmentResultSummary:
    attempt_count: int = 0
    completed_count: int = 0
    best_score: float | None = None
    latest_score: float | None = None
    latest_status: str = ""
    latest_time: object = None
    latest_result_id: int | None = None


@dataclass
class HelpPlanAttemptSummary:
    student_test_id: int | None = None
    score: float | None = None
    end_time: object = None
    answered_count: int = 0
    correct_count: int = 0
    total_questions: int = 0


def _help_plan_related_log_query(plan):
    detail_url = reverse("administrator:help-assignment-detail", args=[plan.student_id, plan.assignment_id])
    delete_url = reverse("administrator:delete-help-plan", args=[plan.id])
    return Q(path__icontains=detail_url) | Q(path__icontains=delete_url)


def _delete_help_plan_logs(plan):
    deleted_count, _ = Log.objects.filter(_help_plan_related_log_query(plan)).delete()
    return deleted_count


def _delete_all_help_logs():
    help_url = reverse("administrator:help-users")
    deleted_count, _ = Log.objects.filter(path__icontains=help_url).delete()
    return deleted_count


def _build_latest_attempt_map(plans):
    if not plans:
        return {}

    student_ids = {plan.student_id for plan in plans}
    assignment_ids = {plan.assignment_id for plan in plans}
    student_tests = (
        StudentTest.objects.filter(
            student_id__in=student_ids,
            assignment_id__in=assignment_ids,
            completed=True,
        )
        .annotate(
            answered_questions_count=Count(
                "student_questions",
                filter=Q(student_questions__selected_answer__isnull=False),
                distinct=True,
            ),
            correct_answers_count=Count(
                "student_questions",
                filter=Q(student_questions__is_correct=True),
                distinct=True,
            ),
            total_questions_count=Count("student_questions", distinct=True),
        )
        .only("id", "student_id", "assignment_id", "score", "end_time")
        .order_by("student_id", "assignment_id", "-end_time", "-id")
    )

    attempt_map = {}
    valid_pairs = {(plan.student_id, plan.assignment_id) for plan in plans}
    for student_test in student_tests:
        pair = (student_test.student_id, student_test.assignment_id)
        if pair not in valid_pairs or pair in attempt_map:
            continue

        attempt_map[pair] = HelpPlanAttemptSummary(
            student_test_id=student_test.id,
            score=student_test.score,
            end_time=student_test.end_time,
            answered_count=student_test.answered_questions_count,
            correct_count=student_test.correct_answers_count,
            total_questions=student_test.total_questions_count,
        )

    return attempt_map


class HelpUserDetailView(HelpAccessMixin, View):
    template_name = "question/views/help-user-detail.html"

    def _build_result_map(self, target_user, assignment_ids):
        result_map: dict[int, AssignmentResultSummary] = {}
        if not assignment_ids:
            return result_map

        student_tests = (
            StudentTest.objects.filter(student=target_user, assignment_id__in=assignment_ids)
            .select_related("assignment__test", "assignment__category")
            .order_by("assignment_id", "-end_time", "-start_time", "-id")
        )

        for student_test in student_tests:
            summary = result_map.setdefault(student_test.assignment_id, AssignmentResultSummary())
            summary.attempt_count += 1
            if student_test.completed:
                summary.completed_count += 1

            if summary.best_score is None or student_test.score > summary.best_score:
                summary.best_score = student_test.score

            if summary.latest_result_id is None:
                summary.latest_result_id = student_test.id
                summary.latest_score = student_test.score
                summary.latest_status = "Yakunlangan" if student_test.completed else "Jarayonda"
                summary.latest_time = student_test.end_time or student_test.start_time

        return result_map

    def get(self, request, user_id):
        target_user = get_object_or_404(
            CustomUser.objects.only(
                "id",
                "username",
                "first_name",
                "second_name",
                "full_name",
                "group_name",
                "profile_picture",
                "is_student",
                "is_teacher",
            ),
            id=user_id,
        )

        assigned_tests = list(
            target_user.assigned_tests.select_related("category")
            .only("id", "name", "category__name")
            .order_by("id")
        )
        assigned_test_ids = [test.id for test in assigned_tests]

        selected_test_id = (request.GET.get("test_id") or "").strip()
        selected_test = None

        if assigned_tests and not selected_test_id:
            selected_test = assigned_tests[0]
            selected_test_id = str(selected_test.id)
        elif selected_test_id.isdigit():
            selected_test = next((test for test in assigned_tests if test.id == int(selected_test_id)), None)

        assignment_options = []
        assignments = []

        if selected_test is not None:
            assignments = list(
                StudentTestAssignment.objects.select_related("test", "category", "teacher")
                .filter(test_id=selected_test.id)
                .order_by("-start_time", "-id")
            )
            assignment_options = assignments

        result_map = self._build_result_map(target_user, [assignment.id for assignment in assignments])
        for assignment in assignments:
            result_summary = result_map.get(assignment.id)
            assignment.student_attempt_count = result_summary.attempt_count if result_summary else 0
            assignment.student_completed_count = result_summary.completed_count if result_summary else 0
            assignment.student_best_score = result_summary.best_score if result_summary else None
            assignment.latest_result_score = result_summary.latest_score if result_summary else None
            assignment.latest_result_status = result_summary.latest_status if result_summary else ""
            assignment.latest_result_time = result_summary.latest_time if result_summary else None
            assignment.latest_result_detail_url = (
                reverse("administrator:view-test-details", args=[result_summary.latest_result_id])
                if result_summary and result_summary.latest_result_id
                else ""
            )

        relevant_results = StudentTest.objects.filter(student=target_user, assignment__test_id__in=assigned_test_ids)
        completed_results = relevant_results.filter(completed=True)
        average_score = completed_results.aggregate(avg_score=Avg("score"))["avg_score"] or 0

        context = {
            "target_user": target_user,
            "assigned_tests": assigned_tests,
            "selected_test_id": selected_test_id,
            "assignments": assignments,
            "stats": {
                "assigned_tests_count": len(assigned_tests),
                "available_assignments_count": len(assignment_options),
                "filtered_assignments_count": len(assignments),
                "results_count": relevant_results.count(),
                "completed_results_count": completed_results.count(),
                "average_score": round(average_score, 1),
            },
        }
        return render(request, self.template_name, context)


class HelpAssignmentDetailView(HelpAccessMixin, View):
    template_name = "question/views/help-assignment-detail.html"

    def _get_target_and_assignment(self, user_id, assignment_id):
        target_user = get_object_or_404(
            CustomUser.objects.only(
                "id",
                "username",
                "first_name",
                "second_name",
                "full_name",
                "group_name",
                "profile_picture",
                "is_student",
                "is_teacher",
            ),
            id=user_id,
        )

        assignment = get_object_or_404(
            StudentTestAssignment.objects.select_related("test", "category", "teacher")
            .annotate(question_bank_count=Count("test__questions", distinct=True))
            .filter(test__students=target_user),
            id=assignment_id,
        )
        return target_user, assignment

    def _build_context(self, target_user, assignment):
        student_tests_queryset = (
            StudentTest.objects.filter(student=target_user, assignment=assignment)
            .annotate(
                answered_questions_count=Count(
                    "student_questions",
                    filter=Q(student_questions__selected_answer__isnull=False),
                    distinct=True,
                ),
                correct_answers_count=Count(
                    "student_questions",
                    filter=Q(student_questions__is_correct=True),
                    distinct=True,
                ),
            )
            .order_by("-end_time", "-start_time", "-id")
        )
        completed_queryset = student_tests_queryset.filter(completed=True)
        help_result_plans = list(
            HelpResultPlan.objects.filter(student=target_user, assignment=assignment)
            .select_related("test", "assignment__test", "created_by")
            .order_by("-created_at", "-id")
        )
        pending_count = sum(1 for plan in help_result_plans if plan.status == HelpResultPlan.STATUS_PENDING)
        completed_count = sum(1 for plan in help_result_plans if plan.status == HelpResultPlan.STATUS_COMPLETED)
        best_plan = max(help_result_plans, key=lambda plan: plan.target_percent, default=None)

        return {
            "target_user": target_user,
            "assignment": assignment,
            "help_result_plans": help_result_plans,
            "status_choices": HelpResultPlan.STATUS_CHOICES,
            "stats": {
                "records_count": len(help_result_plans),
                "pending_count": pending_count,
                "completed_count": completed_count,
                "best_plan": best_plan,
                "attempts_count": student_tests_queryset.count(),
                "student_completed_count": completed_queryset.count(),
                "best_score": completed_queryset.aggregate(best_score=Max("score"))["best_score"],
                "latest_attempt": student_tests_queryset.first(),
            },
        }

    def get(self, request, user_id, assignment_id):
        ensure_help_result_plan_schema()
        target_user, assignment = self._get_target_and_assignment(user_id, assignment_id)
        context = self._build_context(target_user, assignment)
        return render(request, self.template_name, context)

    def post(self, request, user_id, assignment_id):
        ensure_help_result_plan_schema()
        target_user, assignment = self._get_target_and_assignment(user_id, assignment_id)
        redirect_url = reverse("administrator:help-assignment-detail", args=[target_user.id, assignment.id])

        raw_target = (request.POST.get("target_correct_answers") or "").strip()
        status = (request.POST.get("status") or HelpResultPlan.STATUS_PENDING).strip()

        try:
            target_correct_answers = int(raw_target)
        except ValueError:
            messages.error(request, "Kiritiladigan savollar soni butun son bo'lishi kerak.")
            return redirect(redirect_url)

        if target_correct_answers < 0:
            messages.error(request, "Kiritiladigan savollar soni 0 dan kichik bo'lmasligi kerak.")
            return redirect(redirect_url)

        if target_correct_answers > assignment.total_questions:
            messages.error(
                request,
                "Kiritilgan savollar soni topshiriqdagi random savollar sonidan oshmasligi kerak.",
            )
            return redirect(redirect_url)

        if status not in dict(HelpResultPlan.STATUS_CHOICES):
            messages.error(request, "Noto'g'ri status tanlandi.")
            return redirect(redirect_url)

        plan = HelpResultPlan(
            student=target_user,
            assignment=assignment,
            test=assignment.test,
            total_questions=assignment.total_questions,
            target_correct_answers=target_correct_answers,
            status=status,
            created_by=request.user,
        )
        try:
            plan.save()
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect(redirect_url)

        messages.success(request, "Yordam natija qaydi saqlandi.")
        return redirect(redirect_url)
