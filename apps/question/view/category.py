import os
import re
import shutil

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from apps.question.models import Category, Test


DEFAULT_CATEGORY_IMAGE_PATH = os.path.join(
    settings.BASE_DIR,
    "static",
    "assets",
    "images",
    "question_category.png",
)


@method_decorator(login_required, name="dispatch")
class CategoriesView(View):
    template_name = "question/views/categories.html"

    def get(self, request):
        categories = list(
            Category.objects.annotate(tests_count=Count("tests")).order_by("name")
        )
        context = {
            "categories": categories,
            "total_categories_count": len(categories),
            "total_tests_count": sum(category.tests_count for category in categories),
            "empty_categories_count": sum(1 for category in categories if category.tests_count == 0),
            "latest_category_update": max((category.updated_at for category in categories), default=None),
        }
        return render(request, self.template_name, context)

    def delete(self, request, category_id):
        if not request.user.is_superuser:
            return JsonResponse(
                {"success": False, "message": "Sizda bu amalni bajarish uchun ruxsat yo'q."},
                status=403,
            )

        try:
            category = get_object_or_404(Category, id=category_id)
            if category.tests.exists():
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Kategoriyada testlar mavjud, uni o'chirib bo'lmaydi.",
                    },
                    status=400,
                )

            category.delete()
            return JsonResponse(
                {"success": True, "message": "Kategoriya muvaffaqiyatli o'chirildi."}
            )
        except Exception as exc:
            return JsonResponse({"success": False, "message": f"Xato: {exc}"}, status=500)


@method_decorator(login_required, name="dispatch")
class EditCategoryView(View):
    template_name = "question/views/edit-category.html"

    def get(self, request, category_id):
        category = self._get_category(category_id)
        return render(request, self.template_name, {"category": category})

    def post(self, request, category_id):
        category = self._get_category(category_id)
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        image = request.FILES.get("image")

        if not name:
            category.name = name
            category.description = description
            return self._response(
                request,
                success=False,
                message="Kategoriya nomi kiritilishi shart!",
                category=category,
            )

        if Category.objects.filter(name__iexact=name).exclude(id=category.id).exists():
            category.name = name
            category.description = description
            return self._response(
                request,
                success=False,
                message="Bu nomdagi kategoriya allaqachon mavjud.",
                category=category,
            )

        try:
            category.name = name
            category.description = description
            if image:
                category.image = image
            category.save()

            return self._response(
                request,
                success=True,
                message="Kategoriya muvaffaqiyatli yangilandi!",
                category=category,
            )
        except Exception as exc:
            return self._response(
                request,
                success=False,
                message=f"Xatolik yuz berdi: {exc}",
                category=category,
            )

    def _get_category(self, category_id):
        return get_object_or_404(
            Category.objects.annotate(tests_count=Count("tests")),
            id=category_id,
        )

    def _response(self, request, success, message, category):
        payload = {"success": success, "message": message}
        if success:
            payload["redirect_url"] = reverse("administrator:categories")

        if self._is_ajax(request):
            return JsonResponse(payload)
        if success:
            return redirect("administrator:categories")
        return render(request, self.template_name, {"category": category, "error": message})

    def _is_ajax(self, request):
        return request.headers.get("x-requested-with") == "XMLHttpRequest"


@method_decorator(login_required, name="dispatch")
class AddCategoryView(View):
    template_name = "question/views/add-category.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        image = request.FILES.get("image")

        if not name:
            return self._response(
                request,
                success=False,
                message="Kategoriya nomi kiritilishi shart!",
                extra_context={"form_data": {"name": name, "description": description}},
            )

        if Category.objects.filter(name__iexact=name).exists():
            return self._response(
                request,
                success=False,
                message="Bu nomdagi kategoriya allaqachon mavjud.",
                extra_context={"form_data": {"name": name, "description": description}},
            )

        try:
            if image:
                Category.objects.create(
                    name=name,
                    description=description,
                    image=image,
                )
            else:
                new_image_path, filename = self._create_default_image_copy(name)
                with open(new_image_path, "rb") as file_handle:
                    Category.objects.create(
                        name=name,
                        description=description,
                        image=File(file_handle, name=filename),
                    )

            return self._response(
                request,
                success=True,
                message="Kategoriya muvaffaqiyatli qo'shildi!",
            )
        except Exception as exc:
            return self._response(
                request,
                success=False,
                message=f"Xatolik yuz berdi: {exc}",
                extra_context={"form_data": {"name": name, "description": description}},
            )

    def _create_default_image_copy(self, name):
        media_path = os.path.join(settings.MEDIA_ROOT, "category_images")
        os.makedirs(media_path, exist_ok=True)

        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        filename = f"default_{safe_name}.png"
        new_image_path = os.path.join(media_path, filename)
        shutil.copy(DEFAULT_CATEGORY_IMAGE_PATH, new_image_path)
        return new_image_path, filename

    def _response(self, request, success, message, extra_context=None):
        payload = {"success": success, "message": message}
        if success:
            payload["redirect_url"] = reverse("administrator:categories")

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(payload)
        if success:
            return redirect("administrator:categories")

        context = {"error": message}
        if extra_context:
            context.update(extra_context)
        return render(request, self.template_name, context)


class GetCategoryTestsView(View):
    def get(self, request):
        category_id = request.GET.get("category_id")
        if not category_id:
            return JsonResponse(
                {"success": False, "message": "Kategoriya ID berilmadi."},
                status=400,
            )

        tests = Test.objects.filter(category_id=category_id).values("id", "name")
        return JsonResponse({"success": True, "tests": list(tests)}, status=200)


class GetTestQuestionsCountView(View):
    def get(self, request):
        test_id = request.GET.get("test_id")
        if not test_id:
            return JsonResponse({"success": False, "message": "Test ID berilmadi."}, status=400)

        try:
            test = Test.objects.get(id=test_id)
            total_questions = test.questions.count()
            return JsonResponse(
                {"success": True, "total_questions": total_questions},
                status=200,
            )
        except Test.DoesNotExist:
            return JsonResponse({"success": False, "message": "Test topilmadi."}, status=404)
