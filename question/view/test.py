import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from question.forms import TestForm, AddQuestionForm
from question.models import Test, Category, Question, Answer, StudentTestAssignment, StudentQuestion


@method_decorator(login_required, name='dispatch')
class QuestionView(View):
    template_name = 'question/views/questions.html'

    def get(self, request):
        # Filtering parameters
        category_filter = request.GET.get('category', None)  # Filter by category
        search_query = request.GET.get('search', '')  # Search by name

        # Get all tests with question count
        tests_queryset = Test.objects.select_related('category').annotate(
            question_count=Count('questions')
        )

        # Apply filters
        if category_filter:
            tests_queryset = tests_queryset.filter(category__id=category_filter)
        if search_query:
            tests_queryset = tests_queryset.filter(name__icontains=search_query)

        # Pagination
        paginator = Paginator(tests_queryset, 50)  # Show 50 tests per page
        page_number = request.GET.get('page')
        tests = paginator.get_page(page_number)

        # Get all categories for filter dropdown
        categories = Category.objects.all()

        context = {
            'tests': tests,  # Paginated test objects with question counts
            'categories': categories,  # All categories for filtering
            'filters': {
                'category': category_filter,
                'search': search_query,
            },
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class AddQuestionView(View):
    template_name = 'question/views/add-question.html'

    def get(self, request):
        # Fetch categories for the dropdown
        categories = Category.objects.all()

        context = {
            'categories': categories,  # Categories for the dropdown
        }
        return render(request, self.template_name, context)

    def post(self, request):
        # Handle form submission for adding a new test
        category_id = request.POST.get('category')
        name = request.POST.get('name')
        description = request.POST.get('description')

        try:
            category = Category.objects.get(id=category_id)
            Test.objects.create(
                category=category,
                name=name,
                description=description,
                created_by=request.user,
            )
            return JsonResponse({"success": True, "message": "Yangi test muvaffaqiyatli qo'shildi!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"})


@method_decorator(login_required, name='dispatch')
class DeleteTestView(View):
    def delete(self, request, test_id):
        if request.user.is_superuser:  # Only admins can delete tests
            test = get_object_or_404(Test.objects.annotate(
                question_count=Count('questions'),
                result_count=Count('results')
            ), id=test_id)

            # Check if there are related questions or results
            if test.question_count == 0 and test.result_count == 0:
                test.delete()
                return JsonResponse({"success": True, "message": "Test muvaffaqiyatli o‘chirildi!"})
            else:
                return JsonResponse({
                    "success": False,
                    "message": "Testga bog‘langan savollar yoki natijalar mavjudligi sabab o‘chirib bo‘lmaydi."
                })
        return JsonResponse({"success": False, "message": "Ruxsat etilmagan amal!"})


@method_decorator(login_required, name='dispatch')
class EditTestView(View):
    template_name = 'question/views/edit-question.html'

    def get(self, request, test_id):
        # Fetch the test object
        test = get_object_or_404(Test, id=test_id)
        form = TestForm(instance=test)
        context = {
            'form': form,
            'test': test,
        }
        return render(request, self.template_name, context)

    def post(self, request, test_id):
        # Fetch the test object
        test = get_object_or_404(Test, id=test_id)
        form = TestForm(request.POST, instance=test)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True, "message": "Test muvaffaqiyatli yangilandi!"})
        return JsonResponse({"success": False, "message": "Formada xatolik mavjud!"})


@method_decorator(login_required, name='dispatch')
class AddQuestionTestView(View):
    template_name = 'question/views/question-add-test.html'

    def get(self, request, test_id):
        test = get_object_or_404(Test, id=test_id)
        form = AddQuestionForm()

        # Ushbu testga tegishli barcha savollar va ularga tegishli javoblarni olish
        questions = test.questions.prefetch_related('answers')

        context = {
            'form': form,
            'test': test,
            'questions': questions
        }
        return render(request, self.template_name, context)

    def post(self, request, test_id):
        test = get_object_or_404(Test, id=test_id)
        form = AddQuestionForm(request.POST, request.FILES)

        if form.is_valid():
            # Savolni yaratish
            question = Question.objects.create(
                test=test,
                text=form.cleaned_data['text'],
                image=form.cleaned_data['image']
            )

            # Javoblar va ularning atributlarini olish
            answers = request.POST.getlist('answers[]')  # Javob matnlari
            is_correct_flags = request.POST.getlist('is_correct[]')  # To'g'ri yoki noto'g'ri bayrog'i

            # Variantlarni yaratish
            for index, answer_text in enumerate(answers):
                Answer.objects.create(
                    question=question,
                    text=answer_text.strip(),
                    is_correct=(is_correct_flags[index] == 'on' if index < len(is_correct_flags) else False)
                )

            return JsonResponse({"success": True, "message": "Savol va barcha javoblar muvaffaqiyatli saqlandi!"})

        return JsonResponse({"success": False, "errors": form.errors})

@method_decorator(login_required, name='dispatch')
class AssignTestView(View):
    template_name = 'question/views/assign-test.html'

    def get(self, request):
        # Filtr parametrlari
        category_id = request.GET.get('category', None)
        test_name = request.GET.get('test_name', None)
        start_time = request.GET.get('start_time', None)
        end_time = request.GET.get('end_time', None)

        # Hammasini olish yoki filtr qo‘llash
        assignments = StudentTestAssignment.objects.select_related('category', 'test', 'teacher')

        if category_id:
            assignments = assignments.filter(category_id=category_id)
        if test_name:
            assignments = assignments.filter(test__name__icontains=test_name)
        if start_time:
            assignments = assignments.filter(start_time__gte=start_time)
        if end_time:
            assignments = assignments.filter(end_time__lte=end_time)

        # Pagination
        paginator = Paginator(assignments, 50)  # Har bir sahifada 50 ta element
        page_number = request.GET.get('page', 1)
        paginated_assignments = paginator.get_page(page_number)

        # Kategoriyalarni olish
        categories = Category.objects.all()

        context = {
            'assignments': paginated_assignments,
            'categories': categories,
            'filters': {
                'category': category_id,
                'test_name': test_name,
                'start_time': start_time,
                'end_time': end_time,
            },
        }
        return render(request, self.template_name, context)

@method_decorator(login_required, name='dispatch')
class AddAssignTestView(View):
    template_name = 'question/views/add-assign-test.html'

    def get(self, request):
        categories = Category.objects.all()
        return render(request, self.template_name, {'categories': categories})

    def post(self, request):
        category_id = request.POST.get('category')
        test_id = request.POST.get('test')
        total_questions = int(request.POST.get('total_questions'))
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        duration = int(request.POST.get('duration'))

        category = get_object_or_404(Category, id=category_id)
        test = get_object_or_404(Test, id=test_id)

        # Assignment yaratish
        assignment = StudentTestAssignment.objects.create(
            teacher=request.user,
            category=category,
            test=test,
            total_questions=total_questions,
            start_time=start_time,
            end_time=end_time,
            duration=duration
        )

        # Savollar generatsiya qilish
        try:
            questions = assignment.generate_questions()
            for question in questions:
                StudentQuestion.objects.create(
                    assignment=assignment,
                    student=request.user,
                    question=question
                )
        except ValueError as e:
            return JsonResponse({"success": False, "message": str(e)})

        return JsonResponse({"success": True, "message": "Test muvaffaqiyatli tayinlandi!"})

@method_decorator(csrf_exempt, name='dispatch')
class ToggleActiveView(View):
    def post(self, request, assignment_id):
        try:
            data = json.loads(request.body)
            is_active = data.get('is_active', None)

            if is_active is None:
                return JsonResponse({"success": False, "message": "Invalid data received."}, status=400)

            assignment = StudentTestAssignment.objects.get(id=assignment_id)
            assignment.is_active = is_active
            assignment.save()

            status = "activated" if is_active else "deactivated"
            return JsonResponse({"success": True, "message": f"The assignment was successfully {status}."})
        except StudentTestAssignment.DoesNotExist:
            return JsonResponse({"success": False, "message": "Assignment not found."}, status=404)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


class FetchTestsView(View):
    def get(self, request):
        category_id = request.GET.get('category_id')

        # Testlarni va savollar sonini olish
        tests = Test.objects.filter(category_id=category_id).annotate(
            question_count=Count('questions')
        ).values('id', 'name', 'question_count')

        return JsonResponse({'tests': list(tests)})

@method_decorator(login_required, name='dispatch')
class StartTestView(View):
    template_name = 'start_test.html'

    def get(self, request, assignment_id):
        assignment = get_object_or_404(StudentTestAssignment, id=assignment_id, student=request.user)
        questions = assignment.student_questions.select_related('question').prefetch_related('question__answers')
        return render(request, self.template_name, {'assignment': assignment, 'questions': questions})

    def post(self, request, assignment_id):
        assignment = get_object_or_404(StudentTestAssignment, id=assignment_id, student=request.user)
        for question_id, answers in request.POST.items():
            student_question = assignment.student_questions.get(question_id=question_id)
            selected_answers = Answer.objects.filter(id__in=answers)
            student_question.answers.set(selected_answers)
            student_question.check_correctness()
        assignment.status = 'completed'
        assignment.save()
        return JsonResponse({"success": True, "message": "Test yakunlandi!"})