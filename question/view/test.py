import json
import random
from datetime import datetime
from django.db.models import F

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now, make_aware
from question.forms import TestForm, AddQuestionForm
from question.models import Test, Category, Question, Answer, StudentTestAssignment, StudentTest, StudentTestQuestion


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
    def post(self, request, test_id):
        if request.user.is_superuser:  # Only admins can delete tests
            test = get_object_or_404(Test.objects.annotate( question_count=Count('questions')), id=test_id)

            # Check if there are related questions or results
            if test.question_count == 0:
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
        print(f"Test ID: {test_id}, Test: {test}")  # Test ma'lumotini tekshirish

        form = AddQuestionForm(request.POST, request.FILES)
        print(f"POST ma'lumotlari: {request.POST}")  # POST ma'lumotlarini tekshirish
        print(f"Fayllar: {request.FILES}")  # Yuklangan fayllarni tekshirish

        if form.is_valid():
            print("Form validatsiyadan o'tdi!")  # Form validatsiyasi muvaffaqiyatli o'tganini tekshirish

            # Savolni yaratish
            question = Question.objects.create(
                test=test,
                text=form.cleaned_data['text'],
                image=form.cleaned_data.get('image')  # Rasmlar ixtiyoriy
            )
            print(f"Yaratilgan savol: {question}")  # Yaratilgan savolni tekshirish

            # Javoblar va ularning atributlarini olish
            answers = request.POST.getlist('answers[]')  # Javob matnlari
            is_correct_flags = request.POST.getlist('is_correct[]')  # To'g'ri yoki noto'g'ri bayrog'i

            print(f"Answers: {answers}")  # Kiruvchi javoblarni tekshirish
            print(f"Is_correct_flags: {is_correct_flags}")  # To'g'ri javoblar bayrog'ini tekshirish

            # Variantlarni yaratish
            for index, answer_text in enumerate(answers):
                is_correct = is_correct_flags[index].lower() == 'true'
                print(
                    f"Javob: {answer_text.strip()}, To'g'ri: {is_correct}")  # Har bir javobni va uning holatini tekshirish

                Answer.objects.create(
                    question=question,
                    text=answer_text.strip(),
                    is_correct=is_correct
                )

            print("Savol va barcha javoblar muvaffaqiyatli saqlandi!")  # Yakuniy muvaffaqiyat xabari
            return JsonResponse({"success": True, "message": "Savol va barcha javoblar muvaffaqiyatli saqlandi!"})

        print(f"Form validatsiya xatoliklari: {form.errors}")  # Form validatsiyasi xatolarini tekshirish
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
        # Test va kategoriya maʼlumotlarini form uchun yuborish
        categories = Category.objects.all()
        tests = Test.objects.all()
        context = {
            'categories': categories,
            'tests': tests,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        try:
            # POST so‘rovdan maʼlumotlarni olish
            category_id = request.POST.get('category_id')
            test_id = request.POST.get('test_id')
            total_questions = int(request.POST.get('total_questions', 0))
            start_time_str = request.POST.get('start_time')
            end_time_str = request.POST.get('end_time')
            duration = request.POST.get('duration')

            # Ob'yektlarni olish
            category = get_object_or_404(Category, id=category_id)
            test = get_object_or_404(Test, id=test_id)

            # Savollar sonini tekshirish
            available_questions = test.questions.count()
            if total_questions > available_questions:
                return JsonResponse({
                    'success': False,
                    'message': f"Testda faqat {available_questions} ta savol mavjud. Iltimos, mos son kiriting."
                }, status=400)

            # Boshlanish va tugash vaqtlarini formatlash va timezone qo‘shish
            try:
                start_time = make_aware(datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M'))
                end_time = make_aware(datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M'))
            except ValueError:
                return JsonResponse({'success': False, 'message': 'Vaqt noto‘g‘ri formatda kiritilgan.'}, status=400)

            # Vaqtni tekshirish
            if start_time >= end_time:
                return JsonResponse({'success': False, 'message': 'Boshlanish vaqti tugash vaqtidan oldin bo‘lishi kerak.'}, status=400)

            # Mavjud topshiriqni tekshirish
            if StudentTestAssignment.objects.filter(
                category=category,
                test=test,
                start_time=start_time,
                end_time=end_time,
            ).exists():
                return JsonResponse({'success': False, 'message': 'Bunday test topshirig‘i allaqachon mavjud!'}, status=400)

            # Test topshirig‘ini yaratish
            assignment = StudentTestAssignment.objects.create(
                teacher=request.user,
                test=test,
                category=category,
                total_questions=total_questions,
                start_time=start_time,
                end_time=end_time,
                duration=duration,  # Davomiylik daqiqalarda
                is_active=True,
                status='pending'
            )

            return JsonResponse({'success': True, 'message': 'Test topshirig‘i muvaffaqiyatli qo‘shildi!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

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


@method_decorator(login_required, name='dispatch')
class StartTestDetailView(View):
    template_name = 'test/start_test_detail.html'

    def get(self, request, assignment_id):
        # StudentTestAssignment obyektini olish
        assignment = get_object_or_404(StudentTestAssignment, id=assignment_id)

        # Tegishli test, kategoriya va o‘qituvchi maʼlumotlarini olish
        assignment_data = {
            'id': assignment.id,
            'test_name': assignment.test.name,
            'category_name': assignment.category.name,
            'teacher_name': assignment.teacher.full_name,
            'total_questions': assignment.total_questions,
            'start_time': assignment.start_time,
            'end_time': assignment.end_time,
            'duration': assignment.duration,
            'status': assignment.status,
            'is_active': assignment.is_active,
            'created_at': assignment.created_at,
        }

        # Render qilish
        return render(request, self.template_name, {'assignment': assignment_data})

@method_decorator(login_required, name='dispatch')
class StartTestView(View):
    template_name = 'test/start_test.html'

    def get(self, request, assignment_id):
        # StudentTestAssignment ni olish
        assignment = get_object_or_404(StudentTestAssignment, id=assignment_id)

        # Foydalanuvchiga tegishli yakunlanmagan testni qidirish
        unfinished_test = StudentTest.objects.filter(
            student=request.user,
            assignment=assignment,
            completed=False
        ).first()

        if unfinished_test:
            # Mavjud yakunlanmagan testni qayta ochish
            elapsed_time = (now() - unfinished_test.start_time).seconds
            remaining_time = max(0, assignment.duration * 60 - elapsed_time)  # Sekundlarda

            questions_data = []
            for student_question in unfinished_test.student_questions.order_by('order').all():
                answers = list(student_question.question.answers.all())
                questions_data.append({
                    'id': student_question.id,
                    'text': student_question.question.text,
                    'image': student_question.question.image.url if student_question.question.image else None,
                    'answers': [
                        {
                            'id': answer.id,
                            'text': answer.text,
                            'selected': student_question.selected_answer == answer  # Tanlanganmi yoki yo'q
                        }
                        for answer in answers
                    ]
                })

            context = {
                'assignment': assignment,
                'student_test': unfinished_test,
                'questions': questions_data,
                'remaining_time': remaining_time,  # Qolgan vaqtni yuborish
            }
        else:
            # Yangi test yaratish
            student_test = StudentTest.objects.create(
                student=request.user,
                assignment=assignment,
                start_time=now()
            )

            # Savollarni generatsiya qilish va tartibini saqlash
            available_questions = list(assignment.test.questions.all())
            if len(available_questions) < assignment.total_questions:
                return JsonResponse({'success': False, 'message': 'Yetarli savollar mavjud emas.'}, status=400)

            selected_questions = random.sample(available_questions, assignment.total_questions)
            for index, question in enumerate(selected_questions, start=1):
                StudentTestQuestion.objects.create(
                    student_test=student_test,
                    question=question,
                    order=index  # Tartibini saqlash
                )

            questions_data = []
            for student_question in student_test.student_questions.order_by('order').all():
                answers = list(student_question.question.answers.all())
                questions_data.append({
                    'id': student_question.id,
                    'text': student_question.question.text,
                    'image': student_question.question.image.url if student_question.question.image else None,
                    'answers': [
                        {
                            'id': answer.id,
                            'text': answer.text,
                            'selected': False  # Yangi test uchun tanlanmagan
                        }
                        for answer in answers
                    ]
                })

            context = {
                'assignment': assignment,
                'student_test': student_test,
                'questions': questions_data,
                'remaining_time': assignment.duration * 60,  # To'liq vaqt
            }

        return render(request, self.template_name, context)

@method_decorator(login_required, name='dispatch')
class GetRemainingTimeView(View):
    def get(self, request, test_id):
        student_test = get_object_or_404(StudentTest, id=test_id, student=request.user)

        if student_test.completed:
            return JsonResponse({'success': False, 'message': 'Test yakunlangan.'}, status=400)

        assignment = student_test.assignment
        elapsed_time = (now() - student_test.start_time).seconds
        remaining_time = max(0, assignment.duration * 60 - elapsed_time)

        return JsonResponse({'success': True, 'remaining_time': remaining_time})
@method_decorator(login_required, name='dispatch')
class SaveAnswerView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            student_question_id = data.get('student_question_id')
            answer_id = data.get('answer_id')

            # StudentTestQuestion obyektini olish
            student_question = get_object_or_404(StudentTestQuestion, id=student_question_id)
            selected_answer = get_object_or_404(Answer, id=answer_id)

            # Javobni saqlash
            student_question.selected_answer = selected_answer
            student_question.is_correct = selected_answer.is_correct
            student_question.save()

            return JsonResponse({'success': True, 'message': 'Javob muvaffaqiyatli saqlandi!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

@method_decorator(login_required, name='dispatch')
class FinishTestView(View):
    def post(self, request, test_id):
        student_test = get_object_or_404(StudentTest, id=test_id, student=request.user)

        # Testni yakunlash
        correct_answers = student_test.student_questions.filter(is_correct=True).count()
        total_questions = student_test.student_questions.count()
        score = (correct_answers / total_questions) * 100

        student_test.completed = True
        student_test.end_time = now()
        student_test.duration = (student_test.end_time - student_test.start_time).seconds // 60
        student_test.score = score
        student_test.save()

        # Natija sahifasiga yo'naltirish uchun natija URLini qaytarish
        result_url = f"/test/test_result/{student_test.id}/"
        return JsonResponse({'success': True, 'message': f'Test tugatildi. Natijangiz: {score:.2f}%', 'redirect_url': result_url})

@method_decorator(login_required, name='dispatch')
class TestResultView(View):
    template_name = 'test/test_result.html'

    def get(self, request, test_id):
        student_test = get_object_or_404(StudentTest, id=test_id, student=request.user)
        correct_answers = student_test.student_questions.filter(is_correct=True).count()
        total_questions = student_test.student_questions.count()

        context = {
            'student_test': student_test,
            'correct_answers': correct_answers,
            'total_questions': total_questions,
        }
        return render(request, self.template_name, context)