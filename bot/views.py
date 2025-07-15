import base64
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from question.models import StudentTest, StudentTestQuestion, SystemSetting
from django.utils import timezone


@csrf_exempt
def all_test_results(request):
    # Barcha yakunlangan testlarni olish
    student_tests = StudentTest.objects.filter(completed=True).select_related(
        'student', 'assignment__test', 'assignment__category'
    )

    results = []
    for student_test in student_tests:
        # Ball hisoblash
        correct_answers = student_test.student_questions.filter(is_correct=True).count()
        score = correct_answers * 2

        # Talaba ma'lumotlari
        student = student_test.student
        profile_picture = None
        if student.profile_picture:
            try:
                with open(student.profile_picture.path, "rb") as image_file:
                    profile_picture = base64.b64encode(image_file.read()).decode('utf-8')
            except FileNotFoundError:
                profile_picture = None

        # Test va kategoriya ma'lumotlari
        test = student_test.assignment.test
        category = student_test.assignment.category

        # Har bir test uchun natija
        result = {
            "student": {
                "username": student.username,
                "full_name": student.full_name or "",
                "student_id_number": student.student_id_number or "",
                "group_name": student.group_name or "",
                "specialty": student.specialty or "",
                "contact_email": student.contact_email or "",
                "phone_number": student.phone_number or ""
            },
            "test": {
                "name": test.name,
                "category": category.name,
                "total_questions": student_test.assignment.total_questions
            },
            "result": {
                "score": score,
                "correct_answers": correct_answers,
                "duration": student_test.get_duration_display(),
                "completed_at": student_test.end_time.isoformat() if student_test.end_time else None
            }
        }
        results.append(result)

    # HEMIS API'ga yuborish
    system_settings = SystemSetting.objects.filter(is_active=True).first()
    if system_settings and system_settings.hemis_url and system_settings.hemis_api_key:
        headers = {
            "Authorization": f"Bearer {system_settings.hemis_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(system_settings.hemis_url, json={"results": results}, headers=headers)
            response.raise_for_status()
        except requests.RequestException as e:
            return JsonResponse({
                "success": False,
                "message": f"API so'rovida xatolik: {str(e)}",
                "results": results
            })

    return JsonResponse({
        "success": True,
        "results": results
    })