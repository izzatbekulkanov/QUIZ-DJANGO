from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from question.models import Category, StudentTestAssignment, StudentTest, Test, StudentTestQuestion


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
        user_assignments = {a.id: a for a in user_assignments}.values()

        # Har bir topshiriq uchun foydalanuvchi urinishlar sonini olish
        context = {
            'user': user,
            'dark_mode': dark_mode,
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
                    'attempts': StudentTest.objects.filter(assignment=a, student=user).count(),
                    # Foydalanuvchi urinishlari
                    'max_attempts': a.attempts  # Maksimal urinishlar
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
    query = StudentTest.objects.select_related('assignment__category', 'student').filter(
        completed=True, student=user
    ).order_by('-start_time')

    # Filtering
    first_name = request.GET.get('first_name', '').strip()
    second_name = request.GET.get('second_name', '').strip()
    category_id = request.GET.get('category')

    if first_name:
        query = query.filter(student__first_name__icontains=first_name)
    if second_name:
        query = query.filter(student__second_name__icontains=second_name)
    if category_id:
        query = query.filter(assignment__category__id=category_id)

    # Pagination
    paginator = Paginator(query, 50)
    page_number = request.GET.get('page', 1)
    results = paginator.get_page(page_number)

    # Fetch categories for dropdown
    categories = Category.objects.all()

    context = {
        'results': results,
        'categories': categories,
        'first_name': first_name,
        'second_name': second_name,
        'category_id': category_id,
    }
    return render(request, 'test/all_results.html', context)


class ViewResultView(View):
    template_name = 'test/result.html'

    def get(self, request, result_id):
        try:
            result = StudentTest.objects.get(id=result_id, student=request.user)
            questions = StudentTestQuestion.objects.filter(student_test=result).select_related('question', 'selected_answer').prefetch_related('question__answers').order_by('order')
            context = {
                'result': result,
                'questions': questions,
            }
            return render(request, self.template_name, context)
        except StudentTest.DoesNotExist:
            return render(request, self.template_name, {'error': 'Natija topilmadi'})