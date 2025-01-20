from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from datetime import date, timedelta

from django.views.decorators.csrf import csrf_exempt

from account.models import CustomUser
from django.db.models.functions import TruncDate


@method_decorator(login_required, name='dispatch')
class MainView(View):
    template_name = 'question/views/main.html'

    def get(self, request):
        return render(request, self.template_name)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class UsersView(View):
    template_name = 'question/views/users.html'

    def get(self, request):
        search_query = request.GET.get('search', '')
        users_queryset = CustomUser.objects.all()

        # Qidiruv
        if search_query:
            users_queryset = users_queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(second_name__icontains=search_query) |
                Q(phone_number__icontains=search_query) |
                Q(address__icontains=search_query)
            )

        # Pagination
        paginator = Paginator(users_queryset, 50)  # Har sahifada 50 foydalanuvchi
        page_number = request.GET.get('page')
        users = paginator.get_page(page_number)

        # Statistik ma'lumotlar
        today = date.today()
        yesterday = today - timedelta(days=1)
        current_month = today.month

        today_users_count = CustomUser.objects.filter(date_joined__date=today).count()
        yesterday_users_count = CustomUser.objects.filter(date_joined__date=yesterday).count()
        month_users_count = CustomUser.objects.filter(date_joined__month=current_month).count()

        context = {
            'users': users,
            'search_query': search_query,  # Qidiruv so'rovi
            'today_users_count': today_users_count,  # Bugungi foydalanuvchilar
            'yesterday_users_count': yesterday_users_count,  # Kechagi foydalanuvchilar
            'month_users_count': month_users_count,  # Joriy oydagi foydalanuvchilar
        }
        return render(request, self.template_name, context)

    def delete(self, request, id=None):
        # Foydalanuvchini o'chirish
        try:
            user = CustomUser.objects.get(id=id)
            user.delete()
            return JsonResponse({"success": True, "message": "Foydalanuvchi muvaffaqiyatli o'chirildi!"})
        except CustomUser.DoesNotExist:
            return JsonResponse({"success": False, "message": "Foydalanuvchi topilmadi!"}, status=404)
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"}, status=500)
@method_decorator(login_required, name='dispatch')
class AddUserView(View):
    template_name = 'question/views/add-user.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        # Get form data
        first_name = request.POST.get('first_name')
        second_name = request.POST.get('second_name')
        phone_number = request.POST.get('phone_number')
        address = request.POST.get('address')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')
        nationality = request.POST.get('nationality')
        bio = request.POST.get('bio')
        is_teacher = request.POST.get('is_teacher') == 'on'
        is_student = request.POST.get('is_student') == 'on'
        profile_picture = request.FILES.get('profile_picture')
        username = request.POST.get('username')

        default_password = "12345678"

        # Validation errors
        errors = {}

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

        if errors:
            return JsonResponse({"success": False, "errors": errors}, status=400)

        # Save user to database
        try:
            user = CustomUser(
                username=username,
                first_name=first_name,
                second_name=second_name,
                phone_number=phone_number,
                address=address,
                date_of_birth=date_of_birth,
                gender=gender,
                nationality=nationality,
                bio=bio,
                is_teacher=is_teacher,
                is_student=is_student,
                profile_picture=profile_picture
            )
            user.set_password(default_password)
            user.save()
            return JsonResponse({"success": True, "message": "Foydalanuvchi muvaffaqiyatli saqlandi!"}, status=200)
        except ValidationError as e:
            return JsonResponse({"success": False, "message": e.message_dict}, status=400)
        except Exception as e:
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
        return render(request, self.template_name)