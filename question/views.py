import json
import logging
import pickle
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import JsonResponse, StreamingHttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from datetime import date, timedelta
from django.views.decorators.csrf import csrf_exempt
from account.models import CustomUser, FaceEncoding
from logs.models import Log
from question.models import StudentTest, Category, StudentTestQuestion, Test, StudentTestAssignment
from deepface import DeepFace
import os


@method_decorator(login_required, name='dispatch')
class MainView(View):
    template_name = 'question/views/main.html'

    def get(self, request):
        return render(request, self.template_name)


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


try:
    import onnxruntime
    print(f"[INFO] onnxruntime versiyasi: {onnxruntime.__version__}")
except ImportError as e:
    raise ImportError(
        f"onnxruntime o'rnatilmagan yoki Python 3.12.10 bilan mos kelmaydi. `pip install onnxruntime==1.17.3` ni ishlatib ko'ring. Xato: {str(e)}"
    )

User = get_user_model()

class EncodingView(LoginRequiredMixin, View):
    template_name = 'question/views/encoding.html'
    login_url = '/login/'

    def get(self, request):
        # Statistik ma'lumotlar
        stats = [
            {'count': User.objects.filter(is_student=True, face_encoding__isnull=False).count(),
             'label': 'Encoding yaratilgan talabalar'},
            {'count': User.objects.filter(is_student=True, face_encoding__isnull=True).count(),
             'label': 'Encoding yaratilmagan talabalar'},
            {'count': User.objects.filter(is_teacher=True, face_encoding__isnull=False).count(),
             'label': 'Encoding yaratilgan o‘qituvchilar'},
            {'count': User.objects.filter(is_teacher=True, face_encoding__isnull=True).count(),
             'label': 'Encoding yaratilmagan o‘qituvchilar'},
            {'count': User.objects.filter(face_encoding__isnull=False).count(),
             'label': 'Encoding yaratilgan foydalanuvchilar'},
            {'count': User.objects.filter(face_encoding__isnull=True).count(),
             'label': 'Encoding yaratilmagan foydalanuvchilar'},
        ]

        # Guruhlar
        groups = User.objects.filter(
            is_student=True,
            group_name__isnull=False
        ).values('group_name').distinct().order_by('group_name')

        # Foydalanuvchilar va ularning encoding ma'lumotlari
        search_query = request.GET.get('search', '')
        filter_type = request.GET.get('filter_type', '')
        group_id = request.GET.get('group_id', '')

        users = User.objects.all()
        if search_query:
            users = users.filter(
                models.Q(username__icontains=search_query) |
                models.Q(first_name__icontains=search_query) |
                models.Q(second_name__icontains=search_query)
            )
        if filter_type == 'student':
            users = users.filter(is_student=True)
        elif filter_type == 'teacher':
            users = users.filter(is_teacher=True)
        elif filter_type == 'group' and group_id:
            users = users.filter(group_name=group_id, is_student=True)

        # Encoding ma'lumotlari bilan birga foydalanuvchilarni formatlash
        encodings = [
            {
                'user': user,
                'has_encoding': hasattr(user, 'face_encoding') and user.face_encoding is not None
            }
            for user in users
        ]

        # Pagination
        paginator = Paginator(encodings, 50)  # Har bir sahifada 10 ta element
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'stats': stats,
            'groups': groups,
            'encodings': page_obj,
            'search_query': search_query,
            'filter_type': filter_type,
            'group_id': group_id,
            'csrf_token': get_token(request),
        }
        return render(request, self.template_name, context)


def process_user(user):
    try:
        if not hasattr(user.profile_picture, 'file') or not user.profile_picture:
            print(f"[XATO] {user.username} uchun rasm fayli yo‘q")
            return None, f"{user.username} uchun rasm yo‘q"

        image_path = user.profile_picture.path
        if not os.path.exists(image_path):
            print(f"[XATO] Rasm topilmadi: {user.username} - {image_path}")
            return None, f"Rasm topilmadi: {user.username}"

        embedding = DeepFace.represent(img_path=image_path, model_name="ArcFace", enforce_detection=True)[0][
            "embedding"]
        if len(embedding) != 512:
            print(f"[XATO] Noto‘g‘ri embedding uzunligi: {user.username} - kutilgan 512, olingan {len(embedding)}")
            return None, f"Noto‘g‘ri embedding uzunligi: {user.username}"

        return {
            "user": user,
            "encoding": pickle.dumps(embedding),
        }, None
    except Exception as e:
        print(f"[XATO] {user.username} uchun xato: {str(e)}")
        return None, f"{user.username} uchun xato: {str(e)}"


class GenerateEncodingsView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, user_id=None, group_name=None, *args, **kwargs):
        user_type = kwargs.get('user_type')

        def stream():
            try:
                print("[INFO] Encoding yaratish boshlandi...")
                filters = {'profile_picture__isnull': False, 'face_encoding__isnull': True}
                if user_id:
                    filters['id'] = user_id
                    log_msg = f"Foydalanuvchi {user_id}"
                elif group_name:
                    filters['is_student'] = True
                    filters['group_name'] = group_name
                    log_msg = f"Guruh '{group_name}' talabalari"
                elif user_type == 'student':
                    filters['is_student'] = True
                    log_msg = "Talabalar"
                elif user_type == 'teacher':
                    filters['is_teacher'] = True
                    log_msg = "O‘qituvchilar"
                else:
                    log_msg = "Barcha foydalanuvchilar"

                users = User.objects.filter(**filters)
                total_count = users.count()
                total_processed = 0
                print(f"[INFO] Jami {total_count} foydalanuvchi topildi: {log_msg}")

                if total_count == 0:
                    yield f'data: {{"status": "Encoding kerak bo‘lgan {log_msg.lower()} topilmadi", "progress": 100}}\n\n'
                    return

                for user in users:
                    result, error = process_user(user)
                    if error or not result:
                        print(f"[XATO] O‘tkazib yuborildi: {error}")
                        yield f'data: {{"status": "{error}", "progress": {round((total_processed + skipped) / total_count * 100)}}}\n\n'
                        continue

                    with transaction.atomic():
                        # FaceEncoding instansini yaratish yoki yangilash
                        FaceEncoding.objects.update_or_create(
                            user=user,
                            defaults={
                                "encoding": result["encoding"],
                                "encoding_version": "ArcFace",
                                "image_resolution": "112x112",
                                "confidence_score": 0.9,
                            }
                        )

                    total_processed += 1
                    progress = round((total_processed + skipped) / total_count * 100) if total_count else 100
                    yield f'data: {{"status": "{total_processed}/{total_count} {log_msg.lower()} uchun encoding yaratildi", "progress": {progress}}}\n\n'

                status = "success" if skipped == 0 else "partial_success"
                yield f'data: {{"status": "✅ Yakunlandi. {total_processed}/{total_count} {log_msg.lower()} uchun encoding yaratildi, {skipped} o‘tkazib yuborildi", "progress": 100}}\n\n'
            except Exception as e:
                print(f"[XATO] Umumiy xato: {str(e)}")
                yield f'data: {{"status": "❌ Xato: {str(e)}", "progress": 100}}\n\n'

        total_processed = 0
        skipped = 0
        return StreamingHttpResponse(stream(), content_type='text/event-stream')


class DeleteAllEncodingsView(LoginRequiredMixin, View):
    login_url = '/login/'

    def delete(self, request):
        try:
            with transaction.atomic():
                total_count = FaceEncoding.objects.count()
                FaceEncoding.objects.all().delete()
            print(f"[INFO] Jami {total_count} encoding o‘chirildi")
            return JsonResponse({'success': True, 'message': f'Jami {total_count} encoding o‘chirildi'})
        except Exception as e:
            print(f"[XATO] Barcha encodinglarni o‘chirishda xato: {str(e)}")
            return JsonResponse({'success': False, 'message': f'Xato: {str(e)}'}, status=500)


class DeleteFaceEncodingView(LoginRequiredMixin, View):
    login_url = '/login/'

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            FaceEncoding.objects.filter(user=user).delete()
            print(f"[INFO] Foydalanuvchi {user_id} uchun encoding o‘chirildi")
            return JsonResponse({'success': True, 'message': 'Yuz encodingi o‘chirildi'})
        except User.DoesNotExist:
            print(f"[XATO] Foydalanuvchi {user_id} topilmadi")
            return JsonResponse({'success': False, 'message': 'Foydalanuvchi topilmadi'}, status=404)
        except Exception as e:
            print(f"[XATO] Encoding o‘chirishda xato: {str(e)}")
            return JsonResponse({'success': False, 'message': f'Xato: {str(e)}'}, status=500)


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

        default_password = "12345678"

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
        user.date_of_birth = request.POST.get('date_of_birth')
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
        category_id = request.GET.get('category')
        test_name = request.GET.get('test')

        # Base query
        completed_tests = StudentTest.objects.filter(completed=True).select_related(
            'student', 'assignment__test', 'assignment__category'
        ).order_by('-end_time')

        # Apply filters
        if category_id:
            completed_tests = completed_tests.filter(assignment__category_id=category_id)
        if test_name:
            completed_tests = completed_tests.filter(assignment__test__name__icontains=test_name)

        # Fetch categories for the filter dropdown
        categories = Category.objects.all()

        context = {
            'completed_tests': completed_tests,
            'categories': categories,
        }
        return render(request, self.template_name, context)


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
    students = CustomUser.objects.filter(is_student=True).exclude(assigned_tests=test)

    group_filter = request.GET.get('group', '')
    search_query = request.GET.get('search', '')
    if group_filter:
        students = students.filter(group_name=group_filter)
    if search_query:
        students = students.filter(full_name__icontains=search_query)

    groups = CustomUser.objects.filter(is_student=True).values_list('group_name', flat=True).distinct()

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

        redirect_url = reverse('assign-students-to-test', kwargs={'test_id': test_id})
        if query_params:
            redirect_url += '?' + urlencode(query_params)

        if 'remove_student' in request.POST:
            student_id = request.POST.get('remove_student')
            test.students.remove(student_id)
            query_params['alert'] = 'remove_success'
            redirect_url = reverse('assign-students-to-test', kwargs={'test_id': test_id}) + '?' + urlencode(
                query_params)
            return redirect(redirect_url)
        else:
            selected_student_ids = request.POST.getlist('students')
            if selected_student_ids:
                test.students.add(*selected_student_ids)
                query_params['alert'] = 'add_success'
                redirect_url = reverse('assign-students-to-test', kwargs={'test_id': test_id}) + '?' + urlencode(
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
