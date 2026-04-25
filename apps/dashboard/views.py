from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from apps.question.models import Category, StudentTestAssignment, StudentTest, Test, StudentTestQuestion


@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        user = request.user
        dark_mode = request.COOKIES.get('dark_mode', 'false')

        # O‘qituvchi sifatida tayyorlagan, faol topshiriqlar
        teacher_assignments = StudentTestAssignment.objects.filter(
            teacher=user,
            is_active=True,
            end_time__gte=timezone.now()
        ).select_related('test', 'category')

        # Talaba sifatida bog‘langan topshiriqlar
        user_assignments = list(teacher_assignments)

        # Talaba uchun faqat admin tomonidan yaratilgan topshiriqlarni olish
        if user.is_student:
            student_assignments = StudentTestAssignment.objects.filter(
                test__students=user,
                is_active=True,
                end_time__gte=timezone.now()
            ).select_related('test', 'category')
            user_assignments.extend(student_assignments)

        # Id bo‘yicha unikal qilamiz
        user_assignments = list({a.id: a for a in user_assignments}.values())
        assignment_ids = [assignment.id for assignment in user_assignments]

        assignment_attempts = {}
        if assignment_ids:
            student_tests = StudentTest.objects.filter(
                student=user,
                assignment_id__in=assignment_ids
            ).values('assignment_id', 'completed')

            for student_test in student_tests:
                summary = assignment_attempts.setdefault(
                    student_test['assignment_id'],
                    {
                        'attempts': 0,
                        'has_unfinished': False,
                    }
                )
                summary['attempts'] += 1
                if not student_test['completed']:
                    summary['has_unfinished'] = True

        # Statistika ma'lumotlarini hisoblash
        total_assignments = len(user_assignments)
        
        completed_tests = StudentTest.objects.filter(
            student=user,
            completed=True
        ).count()
        
        ongoing_tests = StudentTest.objects.filter(
            student=user,
            completed=False
        ).count()
        
        # O'rtacha ball
        completed_student_tests = StudentTest.objects.filter(
            student=user,
            completed=True
        )
        
        if completed_student_tests.exists():
            total_score = sum([t.score for t in completed_student_tests])
            average_score = int(total_score / completed_student_tests.count())
        else:
            average_score = 0

        # Har bir topshiriq uchun foydalanuvchi urinishlar sonini olish
        context = {
            'user': user,
            'dark_mode': dark_mode,
            'now': timezone.now(),
            'total_tests': total_assignments,
            'completed_tests': completed_tests,
            'ongoing_tests': ongoing_tests,
            'average_score': average_score,
            'user_assignments': [
                {
                    'id': a.id,
                    'test': a.test,
                    'category': a.category,
                    'start_time': a.start_time,
                    'end_time': a.end_time,
                    'duration': a.duration,
                    'total_questions': a.total_questions,  # Admin tomonidan belgilangan savollar soni
                    'is_active': a.is_active,
                    'status': a.status,
                    'attempts': assignment_attempts.get(a.id, {}).get('attempts', 0),
                    # Foydalanuvchi urinishlari
                    'max_attempts': a.attempts,  # Maksimal urinishlar
                    'has_unfinished_attempt': assignment_attempts.get(a.id, {}).get('has_unfinished', False),
                } for a in user_assignments
            ]
        }
        return render(request, 'dashboard/views/main.html', context)


@method_decorator(login_required, name='dispatch')
class CheckUnfinishedTestView(View):
    def get(self, request, assignment_id):
        # Topshiriqni olish
        assignment = get_object_or_404(StudentTestAssignment, id=assignment_id)

        # Foydalanuvchiga tegishli test holatini tekshirish
        test_exists = StudentTest.objects.filter(
            student=request.user,
            assignment_id=assignment_id
        ).exists()

        unfinished_test = StudentTest.objects.filter(
            student=request.user,
            assignment_id=assignment_id,
            completed=False
        ).exists()

        # Urinishlar sonini tekshirish
        attempts_count = StudentTest.objects.filter(
            student=request.user,
            assignment_id=assignment_id
        ).count()

        # Agar urinishlar soni maksimaldan oshsa
        if attempts_count >= assignment.attempts:
            return JsonResponse({
                'never_started': False,
                'unfinished': False,
                'attempts_exceeded': True
            })

        # Agar test umuman boshlanmagan bo'lsa
        if not test_exists:
            return JsonResponse({
                'never_started': True,
                'unfinished': False,
                'attempts_exceeded': False
            })
        # Agar test boshlangan, lekin yakunlanmagan bo'lsa
        elif unfinished_test:
            return JsonResponse({
                'never_started': False,
                'unfinished': True,
                'attempts_exceeded': False
            })
        # Agar test yakunlangan bo'lsa
        else:
            return JsonResponse({
                'never_started': False,
                'unfinished': False,
                'attempts_exceeded': False
            })


@login_required
def all_results(request):
    user = request.user
    base_query = StudentTest.objects.select_related('assignment__category', 'student').filter(
        completed=True, student=user
    )
    query = base_query.order_by('-start_time')

    category_id = request.GET.get('category')

    if category_id:
        query = query.filter(assignment__category__id=category_id)

    # Pagination
    paginator = Paginator(query, 50)
    page_number = request.GET.get('page', 1)
    results = paginator.get_page(page_number)

    # Fetch categories for dropdown
    categories = Category.objects.filter(
        id__in=base_query.values_list('assignment__category_id', flat=True)
    ).order_by('name')

    context = {
        'results': results,
        'categories': categories,
        'category_id': category_id,
    }
    return render(request, 'test/all_results.html', context)


class ViewResultView(View):
    template_name = 'test/result.html'

    def get(self, request, result_id):
        try:
            result = StudentTest.objects.get(id=result_id, student=request.user)
            questions = StudentTestQuestion.objects.filter(student_test=result).select_related('question',
                                                                                               'selected_answer').prefetch_related(
                'question__answers').order_by('order')
            context = {
                'result': result,
                'questions': questions,
            }
            return render(request, self.template_name, context)
        except StudentTest.DoesNotExist:
            return render(request, self.template_name, {'error': 'Natija topilmadi'})
