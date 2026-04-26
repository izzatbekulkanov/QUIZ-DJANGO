from datetime import datetime, timedelta

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from apps.account.models import CustomUser
from apps.logs.models import Log
from apps.question.models import StudentTest, StudentTestAssignment, Test


USERS_STATS_CACHE_TTL = 120
USERS_GROUPS_CACHE_TTL = 300


def _clear_users_cache():
    cache.delete("administrator_users_group_names")
    cache.delete(f"administrator_users_stats:{timezone.localdate().isoformat()}")


def _force_delete_user(user):
    profile_picture = user.profile_picture if user.profile_picture else None

    with transaction.atomic():
        Log.objects.filter(user=user).delete()
        user.delete()

    if profile_picture:
        profile_picture.delete(save=False)


@method_decorator(login_required, name='dispatch')
class UsersView(View):
    template_name = 'question/views/users.html'
    page_size = 30
    list_fields = (
        'id',
        'username',
        'first_name',
        'second_name',
        'full_name',
        'group_name',
        'is_student',
        'is_teacher',
        'is_help',
        'level_name',
        'staff_position',
        'date_of_birth',
        'auth_is_id',
        'profile_picture',
    )

    def _base_queryset(self):
        return CustomUser.objects.only(*self.list_fields)

    def _get_group_names(self):
        cache_key = "administrator_users_group_names"
        cached_groups = cache.get(cache_key)
        if cached_groups is not None:
            return cached_groups

        groups = list(
            CustomUser.objects.exclude(group_name__isnull=True)
            .exclude(group_name__exact='')
            .values_list('group_name', flat=True)
            .distinct()
            .order_by('group_name')
        )
        cache.set(cache_key, groups, USERS_GROUPS_CACHE_TTL)
        return groups

    def _get_summary_stats(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        month_start = today.replace(day=1)
        cache_key = f"administrator_users_stats:{today.isoformat()}"
        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            return cached_stats

        stats = CustomUser.objects.aggregate(
            total_users_count=Count('id'),
            student_users_count=Count('id', filter=Q(is_student=True)),
            teacher_users_count=Count('id', filter=Q(is_teacher=True)),
            auth_enabled_count=Count('id', filter=Q(auth_is_id=True)),
            today_users_count=Count('id', filter=Q(date_joined__date=today)),
            yesterday_users_count=Count('id', filter=Q(date_joined__date=yesterday)),
            month_users_count=Count(
                'id',
                filter=Q(date_joined__date__gte=month_start, date_joined__date__lte=today),
            ),
        )
        cache.set(cache_key, stats, USERS_STATS_CACHE_TTL)
        return stats

    def get(self, request):
        search_query = (request.GET.get('search') or '').strip()
        filter_type = (request.GET.get('filter_type') or '').strip()
        group_name = (request.GET.get('group_name') or request.GET.get('group_id') or '').strip()

        users_queryset = self._base_queryset()
        if search_query:
            users_queryset = users_queryset.filter(
                Q(full_name__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(second_name__icontains=search_query)
                | Q(third_name__icontains=search_query)
                | Q(username__icontains=search_query)
                | Q(phone_number__icontains=search_query)
                | Q(address__icontains=search_query)
                | Q(group_name__icontains=search_query)
            )

        if filter_type == 'student':
            users_queryset = users_queryset.filter(is_student=True)
        elif filter_type == 'teacher':
            users_queryset = users_queryset.filter(is_teacher=True)
        elif filter_type == 'other':
            users_queryset = users_queryset.filter(is_student=False, is_teacher=False)
        elif filter_type == 'group' and group_name:
            users_queryset = users_queryset.filter(group_name=group_name)

        users_queryset = users_queryset.order_by('group_name', 'second_name', 'first_name', 'username')
        groups = self._get_group_names()
        paginator = Paginator(users_queryset, self.page_size)
        users = paginator.get_page(request.GET.get('page'))
        stats = self._get_summary_stats()

        query_params = request.GET.copy()
        query_params.pop('page', None)

        context = {
            'users': users,
            'search_query': search_query,
            'filter_type': filter_type,
            'group_name': group_name,
            'groups': groups,
            'total_users_count': stats['total_users_count'],
            'student_users_count': stats['student_users_count'],
            'teacher_users_count': stats['teacher_users_count'],
            'auth_enabled_count': stats['auth_enabled_count'],
            'today_users_count': stats['today_users_count'],
            'yesterday_users_count': stats['yesterday_users_count'],
            'month_users_count': stats['month_users_count'],
            'pagination_query': query_params.urlencode(),
        }
        return render(request, self.template_name, context)

    def delete(self, request, id=None):
        try:
            user = CustomUser.objects.get(id=id)
            created_tests = Test.objects.filter(created_by=user).count()
            test_assignments = StudentTestAssignment.objects.filter(teacher=user).count()
            student_tests = StudentTest.objects.filter(student=user).count()
            user_logs = Log.objects.filter(user=user).count()

            if created_tests > 0 or test_assignments > 0 or student_tests > 0:
                error_message = "Bu foydalanuvchini o'chirib bo'lmaydi: "
                if created_tests > 0:
                    error_message += f"{created_tests} ta test yaratgan; "
                if test_assignments > 0:
                    error_message += f"{test_assignments} ta test topshirig'i bergan; "
                if student_tests > 0:
                    error_message += f"{student_tests} ta test sinovida ishtirok etgan. "
                if user_logs > 0:
                    error_message += f"{user_logs} ta log yozuvi mavjud."
                return JsonResponse({"success": False, "message": error_message}, status=400)

            user.delete()
            _clear_users_cache()
            return JsonResponse({"success": True, "message": "Foydalanuvchi muvaffaqiyatli o'chirildi!"})
        except CustomUser.DoesNotExist:
            return JsonResponse({"success": False, "message": "Foydalanuvchi topilmadi!"}, status=404)
        except Exception as exc:
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(exc)}"}, status=500)


@method_decorator(login_required, name='dispatch')
class EditUserView(View):
    template_name = 'question/views/edit-user.html'

    def _get_user(self, user_id):
        return get_object_or_404(CustomUser.objects.prefetch_related('groups'), id=user_id)

    def _parse_optional_date(self, raw_value):
        normalized = (raw_value or '').strip()
        normalized = (
            normalized.strip("\"'")
            .replace("\u201c", "")
            .replace("\u201d", "")
            .replace("РІР‚Сљ", "")
            .replace("РІР‚Сњ", "")
            .strip()
        )
        if not normalized:
            return None

        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(normalized, fmt).date()
            except ValueError:
                continue

        raise ValueError("Tug'ilgan sana noto'g'ri formatda. YYYY-MM-DD ko'rinishida bo'lishi kerak.")

    def _parse_optional_int(self, raw_value, error_message):
        value = (raw_value or '').strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(error_message) from exc

    def _build_context(self, user):
        recent_results = list(
            StudentTest.objects.filter(student=user)
            .select_related('assignment__test', 'assignment__category')
            .order_by('-end_time', '-start_time', '-id')[:5]
        )
        completed_results = StudentTest.objects.filter(student=user, completed=True)
        results_summary = completed_results.aggregate(avg_score=Avg('score'))

        return {
            'user': user,
            'role_groups': Group.objects.order_by('name'),
            'selected_role_group_ids': list(user.groups.values_list('id', flat=True)),
            'stats': {
                'assigned_role_groups': user.groups.count(),
                'assigned_tests_count': user.assigned_tests.count(),
                'student_results_count': StudentTest.objects.filter(student=user).count(),
                'completed_results_count': completed_results.count(),
                'average_score': round(results_summary['avg_score'] or 0, 1),
                'managed_tests_count': Test.objects.filter(created_by=user).count(),
                'assignments_count': StudentTestAssignment.objects.filter(teacher=user).count(),
                'logs_count': Log.objects.filter(user=user).count(),
            },
            'recent_results': recent_results,
        }

    def get(self, request, id):
        user = self._get_user(id)
        return render(request, self.template_name, self._build_context(user))

    def post(self, request, id):
        user = self._get_user(id)
        username = (request.POST.get('username') or '').strip()

        if not username:
            return JsonResponse({"success": False, "message": "Username kiritilishi majburiy."}, status=400)
        if CustomUser.objects.exclude(id=user.id).filter(username=username).exists():
            return JsonResponse({"success": False, "message": "Bu username allaqachon band."}, status=400)

        try:
            user.date_of_birth = self._parse_optional_date(request.POST.get('date_of_birth'))
            user.employee_id_number = self._parse_optional_int(
                request.POST.get('employee_id_number'),
                "Xodim ID raqami son bo'lishi kerak.",
            )
        except ValueError as exc:
            return JsonResponse({"success": False, "message": str(exc)}, status=400)

        user.username = username
        user.email = (request.POST.get('email') or '').strip()
        user.contact_email = (request.POST.get('contact_email') or '').strip()
        user.first_name = (request.POST.get('first_name') or '').strip()
        user.second_name = (request.POST.get('second_name') or '').strip()
        user.third_name = (request.POST.get('third_name') or '').strip()
        user.full_name = (request.POST.get('full_name') or '').strip()
        user.phone_number = (request.POST.get('phone_number') or '').strip()
        user.address = (request.POST.get('address') or '').strip()
        user.gender = (request.POST.get('gender') or '').strip() or None
        user.nationality = (request.POST.get('nationality') or '').strip()
        user.citizenship = (request.POST.get('citizenship') or '').strip()
        user.bio = (request.POST.get('bio') or '').strip()
        user.emergency_contact = (request.POST.get('emergency_contact') or '').strip()
        user.is_student = request.POST.get('is_student') == 'on'
        user.is_teacher = request.POST.get('is_teacher') == 'on'
        user.auth_is_id = request.POST.get('auth_is_id') == 'on'
        user.is_help = request.POST.get('is_help') == 'on'

        if request.FILES.get('profile_picture'):
            user.profile_picture = request.FILES['profile_picture']

        user.job_title = (request.POST.get('job_title') or '').strip()
        user.company_name = (request.POST.get('company_name') or '').strip()
        user.department = (request.POST.get('department') or '').strip()
        user.academic_degree = (request.POST.get('academic_degree') or '').strip()
        user.academic_rank = (request.POST.get('academic_rank') or '').strip()
        user.staff_position = (request.POST.get('staff_position') or '').strip()

        user.student_id_number = (request.POST.get('student_id_number') or '').strip()
        user.group_name = (request.POST.get('group_name') or '').strip()
        user.specialty = (request.POST.get('specialty') or '').strip()
        user.specialty_name = (request.POST.get('specialty_name') or '').strip()
        user.education_level = (request.POST.get('education_level') or '').strip()
        user.education_type = (request.POST.get('education_type') or '').strip()
        user.education_form_name = (request.POST.get('education_form_name') or '').strip()
        user.payment_form = (request.POST.get('payment_form') or '').strip()
        user.education_year = (request.POST.get('education_year') or '').strip()
        user.department_name = (request.POST.get('department_name') or '').strip()
        user.level_name = (request.POST.get('level_name') or '').strip()

        if not user.is_teacher:
            user.job_title = None
            user.company_name = None
            user.department = None
            user.academic_degree = None
            user.academic_rank = None
            user.staff_position = None
            user.employee_id_number = None

        if not user.is_student:
            user.student_id_number = None
            user.group_name = None
            user.specialty = None
            user.specialty_name = None
            user.education_level = None
            user.education_type = None
            user.education_form_name = None
            user.payment_form = None
            user.education_year = None
            user.department_name = None
            user.level_name = None

        new_password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        if new_password:
            if new_password != confirm_password:
                return JsonResponse({"success": False, "message": "Parollar mos kelmadi!"}, status=400)
            user.set_password(new_password)

        role_group_ids = [
            int(value)
            for value in request.POST.getlist('role_groups')
            if str(value).strip().isdigit()
        ]

        try:
            user.save()
            user.groups.set(Group.objects.filter(id__in=role_group_ids))
            _clear_users_cache()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Foydalanuvchi muvaffaqiyatli yangilandi!",
                    "redirect_url": reverse('administrator:edit-user', args=[user.id]),
                }
            )
        except Exception as exc:
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(exc)}"}, status=500)


@method_decorator(login_required, name='dispatch')
class ForceDeleteUserView(View):
    def post(self, request, id):
        user = get_object_or_404(CustomUser, id=id)
        is_self_delete = request.user.id == user.id
        confirmation_username = (request.POST.get("confirmation_username") or "").strip()

        if confirmation_username != user.username:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Majburiy o'chirish uchun foydalanuvchining aniq username qiymatini kiriting.",
                },
                status=400,
            )

        try:
            _force_delete_user(user)
            _clear_users_cache()

            if is_self_delete:
                logout(request)

            return JsonResponse(
                {
                    "success": True,
                    "message": "Foydalanuvchi va unga tegishli ma'lumotlar to'liq o'chirildi.",
                    "redirect_url": reverse('login') if is_self_delete else reverse('administrator:users'),
                }
            )
        except Exception as exc:
            return JsonResponse(
                {
                    "success": False,
                    "message": f"Majburiy o'chirishda xatolik yuz berdi: {str(exc)}",
                },
                status=500,
            )
