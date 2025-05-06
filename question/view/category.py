import re
from django.core.files import File  # ✅ MUHIM: File ni shu yerda import qiling
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from question.models import Category, Test
import os
import shutil


@method_decorator(login_required, name='dispatch')
class CategoriesView(View):
    template_name = 'question/views/categories.html'

    def get(self, request):
        # Fetch categories with related tests and questions
        categories = Category.objects.prefetch_related(
            Prefetch('tests', queryset=Test.objects.prefetch_related('questions'))
        )

        context = {
            'categories': categories,
        }
        return render(request, self.template_name, context)

    def delete(self, request, category_id):
        if request.user.is_superuser:  # Only allow admins to delete
            try:
                # Fetch the category or return 404
                category = get_object_or_404(Category, id=category_id)
                print(f"DEBUG: Fetched category with ID {category_id}: {category.name}")

                # Check if the category has related tests
                if not category.tests.exists():
                    print(f"DEBUG: No tests are linked to the category '{category.name}'. Proceeding with deletion.")
                    category.delete()
                    print(f"DEBUG: Category '{category.name}' successfully deleted.")
                    return JsonResponse({"success": True, "message": "Kategoriya muvaffaqiyatli o‘chirildi!"})
                else:
                    print(f"DEBUG: Cannot delete category '{category.name}' as it has linked tests.")
                    return JsonResponse({"success": False,
                                         "message": "Kategoriya tegishli testlar mavjudligi sabab o‘chirib bo‘lmaydi."})
            except Exception as e:
                print(f"ERROR: An error occurred while deleting category ID {category_id}: {str(e)}")
                return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"})
        else:
            print(f"WARNING: Unauthorized delete attempt by user ID {request.user.id} ({request.user.username}).")
            return JsonResponse({"success": False, "message": "Sizda bu amalni bajarish uchun ruxsat yo‘q!"})



@method_decorator(login_required, name='dispatch')
class EditCategoryView(View):
    template_name = 'question/views/edit-category.html'

    def get(self, request, category_id):
        category = get_object_or_404(Category, id=category_id)
        return render(request, self.template_name, {'category': category})

    def post(self, request, category_id):
        category = get_object_or_404(Category, id=category_id)

        name = request.POST.get('name')
        description = request.POST.get('description')
        image = request.FILES.get('image')

        # 🔒 Tekshiruv: nom kiritilganmi
        if not name:
            message = "Kategoriya nomi kiritilishi shart!"
            if self._is_ajax(request):
                return JsonResponse({"success": False, "message": message})
            else:
                return render(request, self.template_name, {
                    "category": category,
                    "error": message
                })

        try:
            category.name = name
            category.description = description
            if image:
                category.image = image
            category.save()

            if self._is_ajax(request):
                return JsonResponse({"success": True, "message": "Kategoriya muvaffaqiyatli yangilandi!"})
            else:
                return redirect('categories')

        except Exception as e:
            message = f"Xatolik yuz berdi: {str(e)}"
            if self._is_ajax(request):
                return JsonResponse({"success": False, "message": message})
            else:
                return render(request, self.template_name, {
                    "category": category,
                    "error": message
                })

    def _is_ajax(self, request):
        return request.headers.get('x-requested-with') == 'XMLHttpRequest'
@method_decorator(login_required, name='dispatch')
class AddCategoryView(View):
    template_name = 'question/views/add-category.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        print("📥 POST so‘rov qabul qilindi.")

        name = request.POST.get('name')
        description = request.POST.get('description')
        image = request.FILES.get('image')

        print(f"➡️  Kiritilgan nom: {name}")
        print(f"➡️  Tavsif: {description}")
        print(f"➡️  Rasm: {'Yuklangan' if image else 'Yuklanmagan'}")

        if not name:
            print("❌ Kategoriya nomi yo‘q!")
            return self._response(request, success=False, message="Kategoriya nomi kiritilishi shart!")

        try:
            # Rasm bo'lmasa — default static rasmni media'ga nusxalash
            if not image:
                print("ℹ️  Rasm yuklanmadi, default static rasmdan foydalaniladi.")

                static_default_path = os.path.join(settings.BASE_DIR, 'static', 'assets', 'images', 'question_category.png')
                media_path = os.path.join(settings.MEDIA_ROOT, 'category_images')
                os.makedirs(media_path, exist_ok=True)

                safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())
                filename = f"default_{safe_name}.png"
                new_image_path = os.path.join(media_path, filename)

                shutil.copy(static_default_path, new_image_path)
                print(f"✅ Default rasm nusxa olindi: {new_image_path}")

                with open(new_image_path, 'rb') as f:
                    image_file = File(f)
                    image_file.name = f'category_images/{filename}'
                    category = Category.objects.create(
                        name=name,
                        description=description,
                        image=image_file,
                    )
                    print(f"✅ Kategoriya yaratildi (default rasm): {category.name}")
            else:
                category = Category.objects.create(
                    name=name,
                    description=description,
                    image=image,
                )
                print(f"✅ Kategoriya yaratildi (upload rasm): {category.name}")

            return self._response(request, success=True, message="Kategoriya muvaffaqiyatli qo'shildi!")

        except Exception as e:
            print(f"❌ Xatolik: {str(e)}")
            return self._response(request, success=False, message=f"Xatolik yuz berdi: {str(e)}")

    def _response(self, request, success, message):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"success": success, "message": message})
        if success:
            return redirect('categories')  # yoki o'zingiz xohlagan sahifa
        return render(request, self.template_name, {"error": message})


class GetCategoryTestsView(View):
    def get(self, request):
        category_id = request.GET.get('category_id')
        if not category_id:
            return JsonResponse({'success': False, 'message': 'Kategoriya ID berilmadi.'}, status=400)

        tests = Test.objects.filter(category_id=category_id).values('id', 'name')
        return JsonResponse({'success': True, 'tests': list(tests)}, status=200)


class GetTestQuestionsCountView(View):
    def get(self, request):
        test_id = request.GET.get('test_id')
        if not test_id:
            return JsonResponse({'success': False, 'message': 'Test ID berilmadi.'}, status=400)

        try:
            test = Test.objects.get(id=test_id)
            total_questions = test.questions.count()  # Testga tegishli savollar soni
            return JsonResponse({'success': True, 'total_questions': total_questions}, status=200)
        except Test.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Test topilmadi.'}, status=404)
