from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View

from question.models import Category, Test


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
        # Kategoriya ma'lumotlarini olish
        category = get_object_or_404(Category, id=category_id)
        context = {
            'category': category,
        }
        return render(request, self.template_name, context)

    def post(self, request, category_id):
        # Kategoriya ma'lumotlarini yangilash
        category = get_object_or_404(Category, id=category_id)
        name = request.POST.get('name')
        description = request.POST.get('description')
        image = request.FILES.get('image', category.image)  # Agar rasm yuborilmagan bo'lsa, eski rasm saqlanadi

        try:
            category.name = name
            category.description = description
            category.image = image
            category.save()
            return JsonResponse({"success": True, "message": "Kategoriya muvaffaqiyatli yangilandi!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"})

@method_decorator(login_required, name='dispatch')
class AddCategoryView(View):
    template_name = 'question/views/add-category.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        name = request.POST.get('name')
        description = request.POST.get('description')
        image = request.FILES.get('image')

        if not name:
            return JsonResponse({"success": False, "message": "Kategoriya nomi kiritilishi shart!"})

        try:
            category = Category.objects.create(
                name=name,
                description=description,
                image=image,
            )
            return JsonResponse({"success": True, "message": "Kategoriya muvaffaqiyatli qo'shildi!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Xatolik yuz berdi: {str(e)}"})


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