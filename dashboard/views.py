from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from question.models import Category, StudentTestAssignment, StudentTest, Test


@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        user = request.user
        dark_mode = request.COOKIES.get('dark_mode', 'false')

        # 1) O‘qituvchi sifatida tayyorlagan, faol topshiriqlar
        teacher_assignments = StudentTestAssignment.objects.filter(
            teacher=user,
            is_active=True,
            end_time__gte=timezone.now()
        ).select_related('test', 'category')

        # 2) Talaba sifatida bog‘langan topshiriqlar
        user_assignments = list(teacher_assignments)
        assigned_tests = (
            Test.objects
            .filter(students=user)
            .select_related('category')
        )

        for test in assigned_tests:
            assignment, _ = StudentTestAssignment.objects.get_or_create(
                test=test,
                teacher=user,
                defaults={
                    'category': test.category,
                    'is_active': True,
                    'start_time': timezone.now(),                     # <— MUHIM!
                    'end_time': timezone.now() + timezone.timedelta(days=7),
                    'duration': 60,
                    'attempts': 3,                                   # modeldagi to‘g‘ri nom
                }
            )
            # Faqat vaqt va holati mos bo‘lsa, ro‘yxatga qo‘shamiz
            if assignment.is_active and assignment.end_time >= timezone.now():
                user_assignments.append(assignment)

        # Id bo‘yicha unikal qilamiz
        user_assignments = {a.id: a for a in user_assignments}.values()

        context = {
            'user': user,
            'dark_mode': dark_mode,
            'user_assignments': user_assignments,
        }
        return render(request, 'dashboard/views/main.html', context)

@method_decorator(login_required, name='dispatch')
class DashboardCategoriesView(View):
    def get(self, request):
        # Barcha kategoriyalarni olish
        categories = Category.objects.all()

        return render(request, 'dashboard/views/categories.html', {
            'user': request.user,
            'categories': categories
        })

@method_decorator(login_required, name='dispatch')
class CategoryAssignmentsView(View):
    template_name = 'dashboard/views/category_assignments.html'

    def get(self, request, category_id):
        # Kategoriyani olish
        category = get_object_or_404(Category, id=category_id)

        # Ushbu kategoriyaga tegishli barcha active va pending assignmentlarni olish
        assignments = StudentTestAssignment.objects.filter(
            category=category,
            is_active=True,  # Faqat active bo'lganlar
            status='pending',  # Faqat pending holatdagilar
            end_time__gt=timezone.now()  # Faqat tugash vaqti hozirgi vaqtga qaraganda keyin bo'lganlar
        ).order_by('-start_time')

        return render(request, self.template_name, {
            'category': category,
            'assignments': assignments,
        })


@method_decorator(login_required, name='dispatch')
class CheckUnfinishedTestView(View):
    def get(self, request, assignment_id):
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

        # Agar test umuman boshlanmagan bo'lsa
        if not test_exists:
            return JsonResponse({'never_started': True, 'unfinished': False})
        # Agar test boshlangan, lekin yakunlanmagan bo'lsa
        elif unfinished_test:
            return JsonResponse({'never_started': False, 'unfinished': True})
        # Agar test yakunlangan bo'lsa
        else:
            return JsonResponse({'never_started': False, 'unfinished': False})

@login_required
def all_results(request):
    user = request.user
    query = StudentTest.objects.select_related('assignment__category', 'student').filter(completed=True, student=user).order_by('-start_time')

    # Filtering
    first_name = request.GET.get('first_name', '').strip()
    second_name = request.GET.get('second_name', '').strip()
    category_id = request.GET.get('category')

    if first_name:
        query = query.filter(student__first_name__icontains=first_name)
    if second_name:
        query = query.filter(student__last_name__icontains=second_name)
    if category_id:
        query = query.filter(assignment__category__id=category_id)

    # Pagination
    paginator = Paginator(query, 50)  # 50 results per page
    page_number = request.GET.get('page', 1)
    results = paginator.get_page(page_number)

    # Fetch categories for dropdown
    categories = Category.objects.all()

    context = {
        'results': results,
        'categories': categories,
    }
    return render(request, 'test/all_results.html', context)