import json
import os
import pickle
import re
import unicodedata
from urllib.parse import urlencode

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Q, Prefetch
from django.http import JsonResponse, StreamingHttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from datetime import date, timedelta, datetime
from openpyxl import load_workbook
from django.views.decorators.csrf import csrf_exempt
from apps.account.models import CustomUser
from apps.logs.models import Log
from apps.question.models import StudentTest, Category, StudentTestQuestion, Test, StudentTestAssignment, Question


DEFAULT_USER_PASSWORD = "namdpi451"


@method_decorator(login_required, name='dispatch')
class MainView(View):
    template_name = 'question/views/main.html'

    def get(self, request):
        # Statistika ma'lumotlarini hisoblash
        total_categories = Category.objects.count()
        total_tests = Test.objects.count()
        total_questions = Question.objects.count()
        total_users = CustomUser.objects.count()
        
        # So'nggi 5 ta testni olish
        recent_tests = Test.objects.all().order_by('-id')[:5]
        
        context = {
            'total_categories': total_categories,
            'total_tests': total_tests,
            'total_questions': total_questions,
            'total_users': total_users,
            'recent_tests': recent_tests,
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    template_name = 'question/views/profile.html'

    def get(self, request):
        user = request.user

        created_tests = (
            Test.objects.filter(created_by=user)
            .select_related('category')
            .order_by('-created_at')
        )
        assignments = (
            StudentTestAssignment.objects.filter(teacher=user)
            .select_related('test', 'category')
            .order_by('-created_at')
        )
        completed_results = (
            StudentTest.objects.filter(assignment__teacher=user, completed=True)
            .select_related('student', 'assignment__test', 'assignment__category')
            .order_by('-end_time')
        )
        recent_logs = Log.objects.filter(user=user).order_by('-timestamp')[:8]

        average_score = completed_results.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        role_labels = []
        if user.is_superuser:
            role_labels.append("Superadmin")
        if user.is_staff and not user.is_superuser:
            role_labels.append("Administrator")
        if getattr(user, "is_teacher", False):
            role_labels.append("O'qituvchi")
        if getattr(user, "is_student", False):
            role_labels.append("Talaba")
        if not role_labels:
            role_labels.append("Foydalanuvchi")

        context = {
            'profile_user': user,
            'role_labels': role_labels,
            'stats': {
                'created_tests': created_tests.count(),
                'active_assignments': assignments.filter(is_active=True).count(),
                'completed_results': completed_results.count(),
                'activity_logs': Log.objects.filter(user=user).count(),
                'managed_students': (
                    StudentTest.objects.filter(assignment__teacher=user)
                    .values('student_id')
                    .distinct()
                    .count()
                ),
                'question_bank_size': Question.objects.filter(test__created_by=user).count(),
                'average_score': round(average_score, 1),
            },
            'recent_tests': created_tests[:5],
            'recent_assignments': assignments[:5],
            'recent_results': completed_results[:5],
            'recent_logs': recent_logs,
        }
        return render(request, self.template_name, context)


@method_decorator(csrf_exempt, name='dispatch')
class ToggleAuthView(View):
    def post(self, request, id):
        try:
            user = CustomUser.objects.get(id=id)
            data = json.loads(request.body)
            user.auth_is_id = data.get('auth_is_id', False)
            user.save()
            return JsonResponse({"success": True, "message": "Autentifikatsiya sozlamasi yangilandi"})
        except CustomUser.DoesNotExist:
            return JsonResponse({"success": False, "message": "Foydalanuvchi topilmadi"}, status=404)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class GrantAllAuthView(View):
    """Barcha foydalanuvchilarga login ruxsatini berish"""
    def post(self, request):
        try:
            updated_count = CustomUser.objects.all().update(auth_is_id=True)
            return JsonResponse({
                "success": True,
                "message": f"{updated_count} ta foydalanuvchiga ruxsat berildi",
                "count": updated_count
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class RevokeAllAuthView(View):
    """Barcha foydalanuvchilardan login ruxsatini olib tashlash"""
    def post(self, request):
        try:
            updated_count = CustomUser.objects.all().update(auth_is_id=False)
            return JsonResponse({
                "success": True,
                "message": f"{updated_count} ta foydalanuvchidan ruxsati olib tashlandi",
                "count": updated_count
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class UsersView(View):
    template_name = 'question/views/users.html'

    def get(self, request):
        search_query = request.GET.get('search', '')
        filter_type = request.GET.get('filter_type', '')
        group_name = request.GET.get('group_name', '')

        users_queryset = CustomUser.objects.all()

        # Qidiruv (to‘liq, username ham kiritilgan)
        if search_query:
            users_queryset = users_queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(second_name__icontains=search_query) |
                Q(username__icontains=search_query) |  # ✅ Username bo‘yicha qidiruv
                Q(phone_number__icontains=search_query) |
                Q(address__icontains=search_query)
            )

        # Filtrlash
        if filter_type == 'student':
            users_queryset = users_queryset.filter(is_student=True)
        elif filter_type == 'teacher':
            users_queryset = users_queryset.filter(is_teacher=True)
        elif filter_type == 'other':
            users_queryset = users_queryset.filter(is_student=False, is_teacher=False)
        elif filter_type == 'group' and group_name:
            users_queryset = users_queryset.filter(group_name=group_name)

        # Saralash
        users_queryset = users_queryset.order_by('second_name', 'group_name')

        # Guruhlar ro‘yxati
        groups = CustomUser.objects.filter(group_name__isnull=False).values('group_name').distinct().order_by(
            'group_name')

        # Pagination
        paginator = Paginator(users_queryset, 50)
        page_number = request.GET.get('page')
        users = paginator.get_page(page_number)

        # Statistik ma'lumotlar
        today = date.today()
        yesterday = today - timedelta(days=1)
        current_month = today.month

        total_users_count = CustomUser.objects.count()
        today_users_count = CustomUser.objects.filter(date_joined__date=today).count()
        yesterday_users_count = CustomUser.objects.filter(date_joined__date=yesterday).count()
        month_users_count = CustomUser.objects.filter(date_joined__month=current_month).count()

        context = {
            'users': users,
            'search_query': search_query,
            'filter_type': filter_type,
            'group_name': group_name,
            'groups': groups,
            'total_users_count': total_users_count,
            'today_users_count': today_users_count,
            'yesterday_users_count': yesterday_users_count,
            'month_users_count': month_users_count,
        }
        return render(request, self.template_name, context)

    def delete(self, request, id=None):
        try:
            user = CustomUser.objects.get(id=id)
            # Bog'liqliklarni tekshirish
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
                    error_message += f"{student_tests} ta test sinovida ishtirok etgan."
                if user_logs > 0:
                    error_message += f"{user_logs} ta log yozuvi mavjud."
                return JsonResponse({
                    "success": False,
                    "message": error_message
                }, status=400)

            user.delete()
            return JsonResponse({
                "success": True,
                "message": "Foydalanuvchi muvaffaqiyatli o'chirildi!"
            })

        except CustomUser.DoesNotExist:
            return JsonResponse({
                "success": False,
                "message": "Foydalanuvchi topilmadi!"
            }, status=404)
        except Exception as e:
            return JsonResponse({
                "success": False,
                "message": f"Xatolik yuz berdi: {str(e)}"
            }, status=500)


@method_decorator(login_required, name='dispatch')
class AddUserView(View):
    template_name = 'question/views/add-user.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        # Forma ma'lumotlarini olish
        first_name = request.POST.get('first_name')
        second_name = request.POST.get('second_name')
        third_name = request.POST.get('third_name')
        phone_number = request.POST.get('phone_number')
        address = request.POST.get('address')
        contact_email = request.POST.get('contact_email')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')
        nationality = request.POST.get('nationality')
        citizenship = request.POST.get('citizenship')
        bio = request.POST.get('bio')
        emergency_contact = request.POST.get('emergency_contact')
        is_teacher = request.POST.get('is_teacher') == 'on'
        is_student = request.POST.get('is_student') == 'on'
        profile_picture = request.FILES.get('profile_picture')
        username = request.POST.get('username')
        job_title = request.POST.get('job_title')
        company_name = request.POST.get('company_name')
        department = request.POST.get('department')
        academic_degree = request.POST.get('academic_degree')
        academic_rank = request.POST.get('academic_rank')
        staff_position = request.POST.get('staff_position')
        student_id_number = request.POST.get('student_id_number')
        group_name = request.POST.get('group_name')
        specialty = request.POST.get('specialty')
        specialty_name = request.POST.get('specialty_name')
        education_level = request.POST.get('education_level')
        education_type = request.POST.get('education_type')
        education_form_name = request.POST.get('education_form_name')
        payment_form = request.POST.get('payment_form')
        education_year = request.POST.get('education_year')
        department_name = request.POST.get('department_name')
        level_name = request.POST.get('level_name')

        # Debug uchun barcha ma'lumotlarni print qilish
        print("=== POST Ma'lumotlari ===")
        print(f"first_name: {first_name}")
        print(f"second_name: {second_name}")
        print(f"third_name: {third_name}")
        print(f"phone_number: {phone_number}")
        print(f"address: {address}")
        print(f"contact_email: {contact_email}")
        print(f"date_of_birth: {date_of_birth}")
        print(f"gender: {gender}")
        print(f"nationality: {nationality}")
        print(f"citizenship: {citizenship}")
        print(f"bio: {bio}")
        print(f"emergency_contact: {emergency_contact}")
        print(f"is_teacher: {is_teacher}")
        print(f"is_student: {is_student}")
        print(f"profile_picture: {profile_picture}")
        print(f"username: {username}")
        print(f"job_title: {job_title}")
        print(f"company_name: {company_name}")
        print(f"department: {department}")
        print(f"academic_degree: {academic_degree}")
        print(f"academic_rank: {academic_rank}")
        print(f"staff_position: {staff_position}")
        print(f"student_id_number: {student_id_number}")
        print(f"group_name: {group_name}")
        print(f"specialty: {specialty}")
        print(f"specialty_name: {specialty_name}")
        print(f"education_level: {education_level}")
        print(f"education_type: {education_type}")
        print(f"education_form_name: {education_form_name}")
        print(f"payment_form: {payment_form}")
        print(f"education_year: {education_year}")
        print(f"department_name: {department_name}")
        print(f"level_name: {level_name}")
        print("====================")

        default_password = DEFAULT_USER_PASSWORD

        # Validatsiya xatoliklari
        errors = {}

        # Asosiy ma'lumotlar validatsiyasi
        if not first_name:
            errors['first_name'] = "Ismni kiritish majburiy."
        if not second_name:
            errors['second_name'] = "Familiyani kiritish majburiy."
        if not username:
            errors['username'] = "Foydalanuvchi nomini kiritish majburiy."
        if not phone_number:
            errors['phone_number'] = "Telefon raqamni kiritish majburiy."
        if not address:
            errors['address'] = "Manzilni kiritish majburiy."
        if not date_of_birth:
            errors['date_of_birth'] = "Tug'ilgan sanani kiritish majburiy."
        if not gender:
            errors['gender'] = "Jinsni tanlash majburiy."
        if not nationality:
            errors['nationality'] = "Millatni kiritish majburiy."
        if not citizenship:
            errors['citizenship'] = "Fuqarolikni kiritish majburiy."

        # O'qituvchi ma'lumotlari validatsiyasi
        if is_teacher:
            if not job_title:
                errors['job_title'] = "Lavozimni kiritish majburiy (o'qituvchi uchun)."
            if not department:
                errors['department'] = "Fakultet/kafedra nomini kiritish majburiy (o'qituvchi uchun)."

        # Talaba ma'lumotlari validatsiyasi
        if is_student:
            if not student_id_number:
                errors['student_id_number'] = "Talaba ID raqamini kiritish majburiy."
            if not group_name:
                errors['group_name'] = "Guruh nomini kiritish majburiy."
            if not specialty:
                errors['specialty'] = "Mutaxassislik kodini kiritish majburiy."
            if not specialty_name:
                errors['specialty_name'] = "Mutaxassislik nomini kiritish majburiy."
            if not education_form_name:
                errors['education_form_name'] = "Ta'lim shaklini kiritish majburiy."
            if not department_name:
                errors['department_name'] = "Fakultet nomini kiritish majburiy."
            if not level_name:
                errors['level_name'] = "Kursni kiritish majburiy."

        if errors:
            print("=== Validatsiya Xatoliklari ===")
            print(errors)
            print("========================")
            return JsonResponse({"success": False, "errors": errors}, status=400)

        # Foydalanuvchini ma'lumotlar bazasiga saqlash
        try:
            user = CustomUser(
                username=username,
                first_name=first_name,
                second_name=second_name,
                third_name=third_name,
                phone_number=phone_number,
                address=address,
                contact_email=contact_email,
                date_of_birth=date_of_birth,
                gender=gender,
                nationality=nationality,
                citizenship=citizenship,
                bio=bio,
                emergency_contact=emergency_contact,
                is_teacher=is_teacher,
                is_student=is_student,
                profile_picture=profile_picture,
                job_title=job_title if is_teacher else None,
                company_name=company_name if is_teacher else None,
                department=department if is_teacher else None,
                academic_degree=academic_degree if is_teacher else None,
                academic_rank=academic_rank if is_teacher else None,
                staff_position=staff_position if is_teacher else None,
                student_id_number=student_id_number if is_student else None,
                group_name=group_name if is_student else None,
                specialty=specialty if is_student else None,
                specialty_name=specialty_name if is_student else None,
                education_level=education_level if is_student else None,
                education_type=education_type if is_student else None,
                education_form_name=education_form_name if is_student else None,
                payment_form=payment_form if is_student else None,
                education_year=education_year if is_student else None,
                department_name=department_name if is_student else None,
                level_name=level_name if is_student else None
            )
            user.set_password(default_password)
            user.save()
            print("=== Foydalanuvchi Muvaffaqiyatli Saqlandi ===")
            print(f"Username: {user.username}")
            print(f"ID: {user.id}")
            print("=================================")
            return JsonResponse({"success": True, "message": "Foydalanuvchi muvaffaqiyatli saqlandi!"}, status=200)
        except ValidationError as e:
            print("=== ValidationError ===")
            print(e.message_dict)
            print("==================")
            return JsonResponse({"success": False, "message": e.message_dict}, status=400)
        except Exception as e:
            print("=== Umumiy Xatolik ===")
            print(str(e))
            print("==================")
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"}, status=500)


@method_decorator(login_required, name='dispatch')
class EditUserView(View):
    template_name = 'question/views/edit-user.html'

    def get(self, request, id):
        # Foydalanuvchini ID bo'yicha topish
        user = get_object_or_404(CustomUser, id=id)
        context = {
            'user': user
        }
        return render(request, self.template_name, context)

    def post(self, request, id):
        # Foydalanuvchini ID bo'yicha topish
        user = get_object_or_404(CustomUser, id=id)

        # Formadan ma'lumotlarni olish
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.second_name = request.POST.get('second_name')
        user.full_name = request.POST.get('full_name')
        user.phone_number = request.POST.get('phone_number')
        user.address = request.POST.get('address')
        dob_raw = (request.POST.get('date_of_birth') or '').strip()
        # Some clients can send empty values as fancy quotes; normalize to empty.
        dob_raw = (
            dob_raw.strip("\"'")
            .replace("\u201c", "")
            .replace("\u201d", "")
            .replace("вЂњ", "")
            .replace("вЂќ", "")
            .strip()
        )
        if not dob_raw:
            user.date_of_birth = None
        else:
            parsed = None
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(dob_raw, fmt).date()
                    break
                except ValueError:
                    continue

            if parsed is None:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Tug'ilgan sana noto'g'ri formatda. YYYY-MM-DD ko'rinishida bo'lishi kerak.",
                    },
                    status=400,
                )

            user.date_of_birth = parsed
        user.gender = request.POST.get('gender')
        user.profile_picture = request.FILES.get('profile_picture', user.profile_picture)
        user.nationality = request.POST.get('nationality')
        user.bio = request.POST.get('bio')
        user.is_student = request.POST.get('is_student') == 'on'
        user.is_teacher = request.POST.get('is_teacher') == 'on'
        user.emergency_contact = request.POST.get('emergency_contact')
        user.job_title = request.POST.get('job_title')
        user.company_name = request.POST.get('company_name')

        # Parolni yangilash
        new_password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        if new_password:
            if new_password == confirm_password:
                user.set_password(new_password)
            else:
                return JsonResponse({"success": False, "message": "Parollar mos kelmadi!"}, status=400)

        # Foydalanuvchini saqlash
        try:
            user.save()
            return JsonResponse({"success": True, "message": "Foydalanuvchi muvaffaqiyatli yangilandi!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"}, status=500)


@method_decorator(login_required, name='dispatch')
class ResultsView(View):
    template_name = 'question/views/results.html'

    def get(self, request):
        # Filters
        category_id = request.GET.get('category', '').strip()
        test_name = request.GET.get('test', '').strip()
        username = request.GET.get('username', '').strip()
        full_name = request.GET.get('full_name', '').strip()

        # Base query
        completed_tests = StudentTest.objects.filter(completed=True).select_related(
            'student', 'assignment__teacher', 'assignment__test', 'assignment__test__created_by', 'assignment__category'
        ).order_by('-end_time')

        # Apply filters
        if category_id:
            completed_tests = completed_tests.filter(assignment__category_id=category_id)
        if test_name:
            completed_tests = completed_tests.filter(assignment__test__name__icontains=test_name)
        if username:
            completed_tests = completed_tests.filter(student__username__icontains=username)
        if full_name:
            name_query = Q(student__full_name__icontains=full_name)
            for term in full_name.split():
                name_query |= (
                    Q(student__first_name__icontains=term)
                    | Q(student__second_name__icontains=term)
                    | Q(student__third_name__icontains=term)
                )
            completed_tests = completed_tests.filter(name_query)

        # Fetch categories for the filter dropdown
        categories = Category.objects.all()

        context = {
            'completed_tests': completed_tests,
            'categories': categories,
            'filters': {
                'category': category_id,
                'test': test_name,
                'username': username,
                'full_name': full_name,
            },
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class DeleteStudentResultView(View):
    def post(self, request, test_id):
        student_test = get_object_or_404(
            StudentTest.objects.select_related('assignment__teacher', 'assignment__test'),
            id=test_id,
        )

        allowed = (
            request.user.is_superuser
            or student_test.assignment.teacher_id == request.user.id
            or student_test.assignment.test.created_by_id == request.user.id
        )
        if not allowed:
            return JsonResponse({"success": False, "message": "Ruxsat yo'q"}, status=403)

        student_label = student_test.student.username
        test_label = student_test.assignment.test.name
        student_test.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"{student_label} uchun '{test_label}' natijasi o'chirildi. Endi qayta urinish mumkin.",
            }
        )


@method_decorator(login_required, name='dispatch')
class ViewTestDetailsView(View):
    template_name = 'question/views/test_details.html'

    def get(self, request, test_id):
        # Fetch the StudentTest object
        test = get_object_or_404(
            StudentTest.objects.prefetch_related(
                Prefetch(
                    'student_questions',
                    queryset=StudentTestQuestion.objects.select_related(
                        'question', 'selected_answer'
                    ).prefetch_related(
                        'question__answers'
                    )
                )
            ),
            id=test_id
        )

        # Calculate statistics
        total_questions = test.student_questions.count()
        correct_answers = test.student_questions.filter(is_correct=True).count()
        incorrect_answers = total_questions - correct_answers

        context = {
            'test': test,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'incorrect_answers': incorrect_answers,
        }

        return render(request, self.template_name, context)


def assign_students_to_test(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    students = CustomUser.objects.filter(is_student=True).exclude(assigned_tests=test).order_by('group_name', 'second_name', 'first_name', 'username')

    group_filter = request.GET.get('group', '')
    search_query = request.GET.get('search', '')
    if group_filter:
        students = students.filter(group_name=group_filter)
    if search_query:
        students = students.filter(
            Q(full_name__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(second_name__icontains=search_query)
            | Q(username__icontains=search_query)
            | Q(student_id_number__icontains=search_query)
        )

    groups_qs = (
        CustomUser.objects.filter(is_student=True, group_name__isnull=False)
        .exclude(group_name="")
        .order_by('group_name')
    )
    groups = list(groups_qs.values_list('group_name', flat=True).distinct())

    paginator = Paginator(students, 40)
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)

    assigned_students = test.students.all()

    if request.method == 'POST':
        query_params = {}
        if group_filter:
            query_params['group'] = group_filter
        if search_query:
            query_params['search'] = search_query
        if page_number:
            query_params['page'] = page_number

        redirect_url = reverse('administrator:assign-students-to-test', kwargs={'test_id': test_id})
        if query_params:
            redirect_url += '?' + urlencode(query_params)

        if 'remove_student' in request.POST:
            student_id = request.POST.get('remove_student')
            test.students.remove(student_id)
            query_params['alert'] = 'remove_success'
            redirect_url = reverse('administrator:assign-students-to-test', kwargs={'test_id': test_id}) + '?' + urlencode(
                query_params)
            return redirect(redirect_url)
        else:
            selected_student_ids = request.POST.getlist('students')
            if selected_student_ids:
                test.students.add(*selected_student_ids)
                query_params['alert'] = 'add_success'
                redirect_url = reverse('administrator:assign-students-to-test', kwargs={'test_id': test_id}) + '?' + urlencode(
                    query_params)
                return redirect(redirect_url)

        return redirect(redirect_url)

    alert = None
    if request.GET.get('alert') == 'add_success':
        alert = {'type': 'success', 'message': 'Talabalar muvaffaqiyatli biriktirildi!'}
    elif request.GET.get('alert') == 'remove_success':
        alert = {'type': 'success', 'message': 'Talaba testdan olib tashlandi!'}

    return render(request, 'question/views/assign_students.html', {
        'test': test,
        'students': students_page,
        'assigned_students': assigned_students,
        'groups': groups,
        'group_filter': group_filter,
        'search_query': search_query,
        'alert': alert,
    })

EXCEL_IMPORT_COLUMN_ALIASES = {
    "username": {
        "username",
        "talabaid",
        "talabaidraqami",
        "studentid",
        "studentidnumber",
        "studentidraqami",
        "tr",
        "id",
    },
    "full_name": {
        "oquvchiningfish",
        "oquvchiningfio",
        "fish",
        "fio",
        "ismfamiliyasiotasiningismi",
        "ismfamiliyaotasiningismi",
    },
    "group_name": {
        "akademikguruh",
        "akademikguruhi",
        "guruh",
        "group",
        "groupname",
    },
}


def _normalize_excel_header(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.casefold()
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _clean_excel_value(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _coerce_excel_username(value):
    text = _clean_excel_value(value)
    if not text:
        return ""

    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return text


def _split_student_full_name(full_name):
    parts = [part for part in full_name.split() if part]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[1], parts[0], ""
    return parts[1], parts[0], " ".join(parts[2:])


def _resolve_excel_columns(columns):
    normalized_columns = {
        _normalize_excel_header(column): column
        for column in columns
    }
    resolved = {}
    for field_name, aliases in EXCEL_IMPORT_COLUMN_ALIASES.items():
        for alias in aliases:
            original_column = normalized_columns.get(alias)
            if original_column:
                resolved[field_name] = original_column
                break
    return resolved


@method_decorator(login_required, name='dispatch')
class ImportUsersExcelView(View):
    required_columns = ("username", "full_name", "group_name")

    def post(self, request):
        excel_file = request.FILES.get("file")
        if not excel_file:
            return JsonResponse({"success": False, "message": "Excel fayl yuklanmadi."}, status=400)
        if not str(excel_file.name or "").lower().endswith((".xlsx", ".xlsm")):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Faqat .xlsx yoki .xlsm formatdagi Excel fayl yuklang.",
                },
                status=400,
            )

        try:
            workbook = load_workbook(excel_file, read_only=True, data_only=True)
            worksheet = workbook.active
            row_iterator = worksheet.iter_rows(values_only=True)
            headers_row = next(row_iterator, None)

            if not headers_row:
                workbook.close()
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Excel fayl bo'sh.",
                    },
                    status=400,
                )

            headers = [header if header is not None else "" for header in headers_row]
            column_map = _resolve_excel_columns(headers)

            missing_columns = [column for column in self.required_columns if column not in column_map]
            if missing_columns:
                workbook.close()
                field_labels = {
                    "username": "username yoki talaba ID",
                    "full_name": "O'quvchining F.I.SH.",
                    "group_name": "akademik guruh",
                }
                missing_labels = ", ".join(field_labels[column] for column in missing_columns)
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Excel ustunlari topilmadi: {missing_labels}.",
                    },
                    status=400,
                )

            prepared_users = {}
            skipped_count = 0

            for row in row_iterator:
                row_data = dict(zip(headers, row))
                username = _coerce_excel_username(row_data.get(column_map["username"]))
                full_name = _clean_excel_value(row_data.get(column_map["full_name"]))
                group_name = _clean_excel_value(row_data.get(column_map["group_name"])) or None

                if not username or not full_name:
                    skipped_count += 1
                    continue

                first_name, second_name, third_name = _split_student_full_name(full_name)
                prepared_users[username] = {
                    "username": username,
                    "student_id_number": username,
                    "first_name": first_name,
                    "second_name": second_name,
                    "third_name": third_name,
                    "full_name": full_name,
                    "group_name": group_name,
                    "is_student": True,
                    "auth_is_id": True,
                }

            workbook.close()

            if not prepared_users:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Import uchun yaroqli foydalanuvchi topilmadi.",
                    },
                    status=400,
                )

            existing_users = {
                user.username: user
                for user in CustomUser.objects.filter(username__in=prepared_users.keys())
            }

            users_to_create = []
            users_to_update = []
            default_password_hash = make_password(DEFAULT_USER_PASSWORD)

            with transaction.atomic():
                for username, payload in prepared_users.items():
                    if username in existing_users:
                        user = existing_users[username]
                        for field_name, value in payload.items():
                            setattr(user, field_name, value)
                        user.password = default_password_hash
                        users_to_update.append(user)
                    else:
                        user = CustomUser(password=default_password_hash, **payload)
                        users_to_create.append(user)

                if users_to_create:
                    CustomUser.objects.bulk_create(users_to_create, batch_size=500)

                if users_to_update:
                    CustomUser.objects.bulk_update(
                        users_to_update,
                        [
                            "username",
                            "student_id_number",
                            "first_name",
                            "second_name",
                            "third_name",
                            "full_name",
                            "group_name",
                            "is_student",
                            "auth_is_id",
                            "password",
                        ],
                        batch_size=500,
                    )

            return JsonResponse(
                {
                    "success": True,
                    "message": (
                        f"Import yakunlandi: {len(users_to_create)} ta qo'shildi, "
                        f"{len(users_to_update)} ta yangilandi, {skipped_count} ta o'tkazib yuborildi."
                    ),
                }
            )
        except Exception as error:
            return JsonResponse(
                {
                    "success": False,
                    "message": f"Importda xatolik yuz berdi: {error}",
                },
                status=500,
            )
