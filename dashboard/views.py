import json
import random
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View

from question.models import Category, StudentTestAssignment, StudentTest


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
class CheckUnfinishedTestView(View):
    def get(self, request, assignment_id):
        # Foydalanuvchiga tegishli yakunlanmagan testni qidirish
        unfinished_test = StudentTest.objects.filter(
            student=request.user,
            assignment_id=assignment_id,
            completed=False
        ).exists()

        return JsonResponse({'unfinished': unfinished_test})

@login_required
def all_results(request):
    query = StudentTest.objects.select_related('assignment__category', 'student').filter(completed=True)

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
    paginator = Paginator(query, 10)  # 10 results per page
    page_number = request.GET.get('page', 1)
    results = paginator.get_page(page_number)

    # Fetch categories for dropdown
    categories = Category.objects.all()

    context = {
        'results': results,
        'categories': categories,
    }
    return render(request, 'test/all_results.html', context)