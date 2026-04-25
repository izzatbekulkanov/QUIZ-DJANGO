from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.account.models import CustomUser
from apps.question.utils.utils import _coerce_import_questions, parse_pasted_questions


class ImportParserTests(SimpleTestCase):
    def test_parse_pasted_questions_accepts_four_character_markers(self):
        pasted_text = """
Jism koordinatasi x0=-7m bo'lgan nuqtadan x o'qi bo'ylab doimiy 6 m/s tezlik bilan harakatlana boshladi. Qancha sekunddan so'ng jismning koordinatasi 5 m bo'ladi?

====#2

====3

====8

====1

++++

Velosipedchi 12 km/soat tezlikda 4 km masofani bosib o'tib, to'xtadi va 40 daqiqa dam oldi. Shundan so'ng qolgan 8 km yo'lni 8 km/soat tezlikda bosib o'tdi. Velosipedchining butun yo'l davomidagi o'rtacha tezligini (km/soat) toping.

====#6

====8

====9

====7

++++

O'q 20 sm qalinlikdagi doskani teshib o'tadi. O'qning doskaga yetib kelishdagi tezligi 200 m/s, doskadan chiqib ketishdagi tezligi esa 100 m/s. O'qning doska ichida harakatlanishidagi tezlanishi (km/s^2 da) qancha?

====#75

====40

====43

====15
""".strip()

        questions = _coerce_import_questions(parse_pasted_questions("", pasted_text))

        self.assertEqual(len(questions), 3)
        self.assertIn("Jism koordinatasi", questions[0]["text"])
        self.assertIn("Velosipedchi", questions[1]["text"])
        self.assertIn("O'q 20 sm", questions[2]["text"])

        self.assertEqual(len(questions[0]["answers"]), 4)
        self.assertEqual(
            [answer["is_correct"] for answer in questions[0]["answers"]],
            [True, False, False, False],
        )
        self.assertIn(">2<", questions[0]["answers"][0]["text"])
        self.assertIn(">6<", questions[1]["answers"][0]["text"])
        self.assertIn(">75<", questions[2]["answers"][0]["text"])


class ImportUsersExcelViewTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="secret123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)

    def _build_excel_file(self, rows):
        workbook = Workbook()
        worksheet = workbook.active
        headers = list(rows[0].keys())
        worksheet.append(headers)
        for row in rows:
            worksheet.append([row.get(header) for header in headers])
        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()
        buffer.seek(0)
        return SimpleUploadedFile(
            "students.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_import_creates_login_ready_student_from_excel(self):
        upload = self._build_excel_file(
            [
                {
                    "username": 4440123456807,
                    "O‘quvchining F.I.SH.": "Aliyeva Gulsanam Elmurod qizi",
                    "akademik guruh": "Biologiya",
                }
            ]
        )

        response = self.client.post(
            reverse("administrator:import-users-excel"),
            {"file": upload},
        )

        self.assertEqual(response.status_code, 200)
        student = CustomUser.objects.get(username="4440123456807")
        self.assertEqual(student.student_id_number, "4440123456807")
        self.assertEqual(student.first_name, "Gulsanam")
        self.assertEqual(student.second_name, "Aliyeva")
        self.assertEqual(student.third_name, "Elmurod qizi")
        self.assertEqual(student.group_name, "Biologiya")
        self.assertTrue(student.is_student)
        self.assertTrue(student.auth_is_id)
        self.assertTrue(student.check_password("namdpi451"))

    def test_import_updates_existing_student_and_resets_default_password(self):
        student = CustomUser.objects.create_user(
            username="4440123456798",
            password="old-password",
            auth_is_id=False,
        )
        upload = self._build_excel_file(
            [
                {
                    "username": "4440123456798",
                    "O'quvchining F.I.SH.": "Abduraufova Rayxona Zohirxon qizi",
                    "akademik guruhi": "Biologiya",
                }
            ]
        )

        response = self.client.post(
            reverse("administrator:import-users-excel"),
            {"file": upload},
        )

        self.assertEqual(response.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.first_name, "Rayxona")
        self.assertEqual(student.second_name, "Abduraufova")
        self.assertEqual(student.third_name, "Zohirxon qizi")
        self.assertEqual(student.group_name, "Biologiya")
        self.assertEqual(student.student_id_number, "4440123456798")
        self.assertTrue(student.is_student)
        self.assertTrue(student.auth_is_id)
        self.assertTrue(student.check_password("namdpi451"))
