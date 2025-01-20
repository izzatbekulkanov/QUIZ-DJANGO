from datetime import timedelta

from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View

from question.models import Category, StudentTestAssignment


@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        dark_mode = request.COOKIES.get('dark_mode', 'false')
        return render(request, 'dashboard/views/main.html', {
            'user': request.user,
            'dark_mode': dark_mode,
        })

@method_decorator(login_required, name='dispatch')
class DashboardCategoriesView(View):
    def get(self, request):
        # Kategoriyalarga bog‘liq faqat active bo‘lgan `StudentTestAssignment`larni olish
        categories = Category.objects.prefetch_related(
            Prefetch(
                'test_assignments',
                queryset=StudentTestAssignment.objects.filter(is_active=True)
            )
        ).filter(test_assignments__is_active=True).distinct()  # Faqat assignment birikkan kategoriyalarni olish

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
class StartTestView(View):
    template_name = 'test/start_test.html'

    def get(self, request, assignment_id):
        assignment = get_object_or_404(StudentTestAssignment, id=assignment_id, is_active=True, status='pending')


        # Savollarni tayyorlash
        questions = assignment.test.questions.all()
        return render(request, self.template_name, {
            'assignment': assignment,
            'questions': questions,
        })