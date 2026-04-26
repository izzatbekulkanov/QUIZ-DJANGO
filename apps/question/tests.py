from io import BytesIO
from datetime import timedelta

from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from apps.account.models import CustomUser
from apps.question.models import Answer, Category, Question, StudentTest, StudentTestAssignment, StudentTestQuestion, Test
from apps.question.utils.utils import _coerce_import_questions, parse_pasted_questions
from apps.question.views import _delete_excel_import_preview


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

    def test_parse_pasted_questions_accepts_split_answer_markers(self):
        pasted_text = """
++++
Wie heißt du?
====
#Ich heiße Anna.
====
Ich wohne Anna.
====
Ich komme Anna.
====
Ich bin Anna wohne.
++++
Ich komme ___ Italien.
====
#aus
====
in
====
bei
====
von
""".strip()

        questions = _coerce_import_questions(parse_pasted_questions("", pasted_text))

        self.assertEqual(len(questions), 2)
        self.assertIn("Wie heißt du?", questions[0]["text"])
        self.assertIn("Ich komme ___ Italien.", questions[1]["text"])
        self.assertEqual(len(questions[0]["answers"]), 4)
        self.assertEqual(len(questions[1]["answers"]), 4)
        self.assertTrue(questions[0]["answers"][0]["is_correct"])
        self.assertTrue(questions[1]["answers"][0]["is_correct"])
        self.assertIn("Ich heiße Anna.", questions[0]["answers"][0]["text"])
        self.assertIn(">aus<", questions[1]["answers"][0]["text"])


    def test_parse_pasted_questions_accepts_variable_marker_counts(self):
        pasted_text = """
+
Ich ___ Lehrer.
=
##bin
=
kommen
=
heißen
=
spricht
+
„goodbye“ =
==
###Auf Wiedersehen
==
Danke
""".strip()

        questions = _coerce_import_questions(parse_pasted_questions("", pasted_text))

        self.assertEqual(len(questions), 2)
        self.assertIn("Ich ___ Lehrer.", questions[0]["text"])
        self.assertIn("„goodbye“ =", questions[1]["text"])
        self.assertEqual(len(questions[0]["answers"]), 4)
        self.assertEqual(len(questions[1]["answers"]), 2)
        self.assertTrue(questions[0]["answers"][0]["is_correct"])
        self.assertTrue(questions[1]["answers"][0]["is_correct"])
        self.assertIn(">bin<", questions[0]["answers"][0]["text"])
        self.assertIn("Auf Wiedersehen", questions[1]["answers"][0]["text"])

    def test_parse_pasted_questions_prefers_plain_text_when_html_collapses_lines(self):
        pasted_text = """
+++
Wie heiГџt du?
====
#Ich heiГџe Anna.
====
Ich wohne Anna.
====
Ich komme Anna.
====
Ich bin Anna wohne.
+++
Ich komme ___ Italien.
====
#aus
====
in
====
bei
====
von
""".strip()
        pasted_html = """
<div>
  <p>++++<br>Wie heiГџt du?<br>====<br>#Ich heiГџe Anna.<br>====<br>Ich wohne Anna.<br>====<br>Ich komme Anna.<br>====<br>Ich bin Anna wohne.</p>
  <p>++++<br>Ich komme ___ Italien.<br>====<br>#aus<br>====<br>in<br>====<br>bei<br>====<br>von</p>
</div>
""".strip()

        questions = _coerce_import_questions(parse_pasted_questions(pasted_html, pasted_text))

        self.assertEqual(len(questions), 2)
        self.assertEqual(len(questions[0]["answers"]), 4)
        self.assertEqual(len(questions[1]["answers"]), 4)
        self.assertTrue(questions[0]["answers"][0]["is_correct"])
        self.assertTrue(questions[1]["answers"][0]["is_correct"])


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

    def _build_excel_file_with_offset_headers(self, rows, blank_rows=1, use_second_sheet=False):
        workbook = Workbook()
        first_sheet = workbook.active

        if use_second_sheet:
            first_sheet.title = "Bo'sh varaq"
            worksheet = workbook.create_sheet(title="Import")
        else:
            worksheet = first_sheet

        for _ in range(blank_rows):
            worksheet.append([])

        headers = list(rows[0].keys())
        worksheet.append(headers)
        for row in rows:
            worksheet.append([row.get(header) for header in headers])

        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()
        buffer.seek(0)
        return SimpleUploadedFile(
            "students-offset.xlsx",
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

    def test_preview_endpoint_returns_summary_and_token(self):
        upload = self._build_excel_file(
            [
                {
                    "username": "4440123456701",
                    "O'quvchining F.I.SH.": "Karimov Azizbek Alisher o'g'li",
                    "akademik guruh": "Tarix",
                }
            ]
        )

        response = self.client.post(
            reverse("administrator:import-users-excel-preview"),
            {"file": upload},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["summary"]["total_valid"], 1)
        self.assertEqual(payload["summary"]["new_count"], 1)
        self.assertEqual(payload["summary"]["update_count"], 0)
        self.assertEqual(payload["preview_rows"][0]["username"], "4440123456701")
        _delete_excel_import_preview(payload["token"])

    def test_stream_endpoint_imports_users_from_preview_token(self):
        upload = self._build_excel_file(
            [
                {
                    "username": "4440123456702",
                    "O'quvchining F.I.SH.": "Usmonova Dilnoza Xamid qizi",
                    "akademik guruh": "Matematika",
                }
            ]
        )

        preview_response = self.client.post(
            reverse("administrator:import-users-excel-preview"),
            {"file": upload},
        )
        self.assertEqual(preview_response.status_code, 200)
        token = preview_response.json()["token"]

        response = self.client.get(
            reverse("administrator:import-users-excel-stream"),
            {"token": token},
        )

        self.assertEqual(response.status_code, 200)
        stream_content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn('"success": true', stream_content.lower())
        self.assertIn('"progress": 100', stream_content)

        student = CustomUser.objects.get(username="4440123456702")
        self.assertEqual(student.first_name, "Dilnoza")
        self.assertEqual(student.second_name, "Usmonova")
        self.assertEqual(student.group_name, "Matematika")
        self.assertTrue(student.check_password("namdpi451"))

    def test_import_finds_headers_after_blank_rows_and_non_active_sheet(self):
        upload = self._build_excel_file_with_offset_headers(
            [
                {
                    "username": "4440123456703",
                    "O'quvchining F.I.SH.": "Tojiboyeva Nilufar Shavkat qizi",
                    "akademik guruh": "Biologiya",
                }
            ],
            blank_rows=2,
            use_second_sheet=True,
        )

        response = self.client.post(
            reverse("administrator:import-users-excel-preview"),
            {"file": upload},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["summary"]["total_valid"], 1)
        self.assertEqual(payload["preview_rows"][0]["username"], "4440123456703")
        _delete_excel_import_preview(payload["token"])


class ResultsViewTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="results-admin",
            password="secret123",
            is_staff=True,
        )
        self.student = CustomUser.objects.create_user(
            username="student1",
            password="secret123",
            is_student=True,
            first_name="Ali",
            second_name="Valiyev",
        )
        self.client.force_login(self.admin_user)

        self.category = Category.objects.create(name="Matematika")
        self.test = Test.objects.create(
            category=self.category,
            name="Algebra testi",
            created_by=self.admin_user,
        )
        Question.objects.create(test=self.test, text="2+2=?")

        now = timezone.now()
        self.assignment = StudentTestAssignment.objects.create(
            teacher=self.admin_user,
            test=self.test,
            category=self.category,
            total_questions=1,
            start_time=now - timedelta(hours=2),
            end_time=now + timedelta(hours=2),
            duration=30,
        )

        self.completed_today = StudentTest.objects.create(
            student=self.student,
            assignment=self.assignment,
            completed=True,
            duration=180,
            score=88,
        )
        self.completed_today.start_time = now - timedelta(hours=1)
        self.completed_today.end_time = now
        self.completed_today.save(update_fields=["start_time", "end_time"])

        self.incomplete_today = StudentTest.objects.create(
            student=self.student,
            assignment=self.assignment,
            completed=False,
            duration=0,
            score=0,
        )
        self.incomplete_today.start_time = now - timedelta(minutes=20)
        self.incomplete_today.end_time = None
        self.incomplete_today.save(update_fields=["start_time", "end_time"])

        self.completed_yesterday = StudentTest.objects.create(
            student=self.student,
            assignment=self.assignment,
            completed=True,
            duration=240,
            score=72,
        )
        self.completed_yesterday.start_time = now - timedelta(days=1, hours=1)
        self.completed_yesterday.end_time = now - timedelta(days=1)
        self.completed_yesterday.save(update_fields=["start_time", "end_time"])

    def test_results_view_defaults_to_today_and_includes_incomplete_tests(self):
        response = self.client.get(reverse("administrator:results"))

        self.assertEqual(response.status_code, 200)
        student_tests = list(response.context["student_tests"])
        self.assertIn(self.completed_today, student_tests)
        self.assertIn(self.incomplete_today, student_tests)
        self.assertNotIn(self.completed_yesterday, student_tests)
        self.assertEqual(response.context["filters"]["time_filter"], "today")
        self.assertEqual(response.context["filters"]["status"], "all")

    def test_results_view_can_filter_by_incomplete_status_and_all_time(self):
        response = self.client.get(
            reverse("administrator:results"),
            {"status": "incomplete", "time_filter": "all"},
        )

        self.assertEqual(response.status_code, 200)
        student_tests = list(response.context["student_tests"])
        self.assertEqual(student_tests, [self.incomplete_today])


class RoleGroupManagementTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="roles-admin",
            password="secret123",
            is_staff=True,
            is_superuser=True,
        )
        self.student_user = CustomUser.objects.create_user(
            username="role-student",
            password="secret123",
            is_student=True,
            first_name="Ali",
            second_name="Karimov",
        )
        self.staff_user = CustomUser.objects.create_user(
            username="role-staff",
            password="secret123",
            is_teacher=True,
            first_name="Vali",
            second_name="Bekov",
        )
        self.client.force_login(self.admin_user)
        self.permissions = list(Permission.objects.order_by("id")[:2])

    def test_add_role_group_creates_group_with_selected_permissions(self):
        response = self.client.post(
            reverse("administrator:add-role-group"),
            {
                "name": "Nazoratchilar",
                "permissions": [permission.id for permission in self.permissions[:1]],
            },
        )

        role_group = Group.objects.get(name="Nazoratchilar")
        self.assertRedirects(
            response,
            reverse("administrator:role-group-detail", args=[role_group.id]),
        )
        self.assertEqual(role_group.permissions.count(), 1)
        self.assertEqual(role_group.permissions.first(), self.permissions[0])

    def test_role_group_detail_updates_permissions_and_users(self):
        role_group = Group.objects.create(name="Operatorlar")

        response = self.client.post(
            reverse("administrator:role-group-detail", args=[role_group.id]),
            {
                "name": "Operatorlar Plus",
                "permissions": [permission.id for permission in self.permissions],
                "users": [self.student_user.id, self.staff_user.id],
            },
        )

        self.assertRedirects(
            response,
            reverse("administrator:role-group-detail", args=[role_group.id]),
        )

        role_group.refresh_from_db()
        self.assertEqual(role_group.name, "Operatorlar Plus")
        self.assertEqual(
            set(role_group.permissions.values_list("id", flat=True)),
            {permission.id for permission in self.permissions},
        )
        self.assertEqual(
            set(role_group.user_set.values_list("id", flat=True)),
            {self.student_user.id, self.staff_user.id},
        )

    def test_role_user_search_returns_matching_username(self):
        response = self.client.get(
            reverse("administrator:role-user-search"),
            {"q": "role-stud"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["username"], "role-student")

    def test_create_default_role_groups_creates_recommended_groups(self):
        response = self.client.post(reverse("administrator:create-default-role-groups"))

        self.assertRedirects(response, reverse("administrator:roles"))
        self.assertTrue(Group.objects.filter(name="Super Administrator").exists())
        self.assertTrue(Group.objects.filter(name="System Administrator").exists())
        self.assertTrue(Group.objects.filter(name="Academic Operations Manager").exists())
        self.assertTrue(Group.objects.filter(name="Standard User").exists())

    def test_superuser_can_delete_role_group(self):
        role_group = Group.objects.create(name="Delete Me")

        response = self.client.post(reverse("administrator:delete-role-group", args=[role_group.id]))

        self.assertRedirects(response, reverse("administrator:roles"))
        self.assertFalse(Group.objects.filter(id=role_group.id).exists())

    def test_super_administrator_role_can_delete_role_group(self):
        self.client.logout()
        role_super_admin = Group.objects.create(name="Super Administrator")
        delegated_admin = CustomUser.objects.create_user(
            username="delegated-admin",
            password="secret123",
            is_staff=True,
        )
        delegated_admin.groups.add(role_super_admin)
        role_group = Group.objects.create(name="Delegated Delete")

        self.client.force_login(delegated_admin)
        response = self.client.post(reverse("administrator:delete-role-group", args=[role_group.id]))

        self.assertRedirects(response, reverse("administrator:roles"))
        self.assertFalse(Group.objects.filter(id=role_group.id).exists())


class EditUserAdminViewTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="edit-admin",
            password="secret123",
            is_staff=True,
            is_superuser=True,
        )
        self.target_user = CustomUser.objects.create_user(
            username="edit-target",
            password="secret123",
            is_student=True,
            first_name="Ali",
            second_name="Valiyev",
            group_name="Old Group",
        )
        self.role_group = Group.objects.create(name="Academic Operations Manager")
        self.client.force_login(self.admin_user)

    def test_edit_user_updates_group_and_role_groups(self):
        response = self.client.post(
            reverse("administrator:edit-user", args=[self.target_user.id]),
            {
                "username": "edit-target",
                "first_name": "Ali",
                "second_name": "Valiyev",
                "full_name": "Ali Valiyev",
                "phone_number": "998901234567",
                "email": "ali@example.com",
                "contact_email": "ali@example.com",
                "group_name": "Yangi Group",
                "is_student": "on",
                "auth_is_id": "on",
                "role_groups": [self.role_group.id],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])

        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.group_name, "Yangi Group")
        self.assertEqual(
            list(self.target_user.groups.values_list("id", flat=True)),
            [self.role_group.id],
        )


class ViewTestDetailsViewTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="detail-admin",
            password="secret123",
            is_staff=True,
        )
        self.student = CustomUser.objects.create_user(
            username="detail-student",
            password="secret123",
            is_student=True,
            full_name="Test Student",
        )
        self.client.force_login(self.admin_user)

        self.category = Category.objects.create(name="Fizika")
        self.test = Test.objects.create(
            category=self.category,
            name="Mexanika",
            created_by=self.admin_user,
        )

        question_one = Question.objects.create(test=self.test, text="1-savol")
        question_two = Question.objects.create(test=self.test, text="2-savol")
        question_three = Question.objects.create(test=self.test, text="3-savol")

        correct_one = Answer.objects.create(question=question_one, text="A", is_correct=True)
        Answer.objects.create(question=question_one, text="B", is_correct=False)
        Answer.objects.create(question=question_two, text="A", is_correct=True)
        wrong_two = Answer.objects.create(question=question_two, text="B", is_correct=False)
        Answer.objects.create(question=question_three, text="A", is_correct=True)
        Answer.objects.create(question=question_three, text="B", is_correct=False)

        now = timezone.now()
        self.assignment = StudentTestAssignment.objects.create(
            teacher=self.admin_user,
            test=self.test,
            category=self.category,
            total_questions=3,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            duration=30,
        )
        self.student_test = StudentTest.objects.create(
            student=self.student,
            assignment=self.assignment,
            completed=False,
            duration=95,
            score=0,
        )

        StudentTestQuestion.objects.create(
            student_test=self.student_test,
            question=question_one,
            selected_answer=correct_one,
            is_correct=True,
            order=2,
        )
        StudentTestQuestion.objects.create(
            student_test=self.student_test,
            question=question_two,
            selected_answer=wrong_two,
            is_correct=False,
            order=1,
        )
        StudentTestQuestion.objects.create(
            student_test=self.student_test,
            question=question_three,
            selected_answer=None,
            is_correct=False,
            order=3,
        )

    def test_view_test_details_builds_clear_summary_context(self):
        response = self.client.get(
            reverse("administrator:view-test-details", args=[self.student_test.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_questions"], 3)
        self.assertEqual(response.context["answered_count"], 2)
        self.assertEqual(response.context["correct_answers"], 1)
        self.assertEqual(response.context["incorrect_answers"], 1)
        self.assertEqual(response.context["unanswered_count"], 1)
        self.assertEqual(response.context["progress_percent"], 66.7)
        self.assertEqual(response.context["accuracy_percent"], 50.0)
        self.assertEqual(
            [row.order for row in response.context["question_rows"]],
            [1, 2, 3],
        )


class AddAssignTestViewTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="assign-admin",
            password="secret123",
            is_staff=True,
        )
        self.client.force_login(self.admin_user)
        self.category = Category.objects.create(name="Kimyo")
        self.test = Test.objects.create(
            category=self.category,
            name="Organik kimyo",
            created_by=self.admin_user,
        )
        Question.objects.create(test=self.test, text="Savol 1")

    def test_add_assignment_allows_past_start_time(self):
        now = timezone.now()
        response = self.client.post(
            reverse("administrator:add-assign-test"),
            {
                "category_id": self.category.id,
                "test_id": self.test.id,
                "total_questions": 1,
                "start_time": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
                "end_time": (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"),
                "duration": 30,
                "max_attempts": 3,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentTestAssignment.objects.count(), 1)
        assignment = StudentTestAssignment.objects.get()
        self.assertEqual(assignment.teacher_id, self.admin_user.id)
        self.assertEqual(assignment.test_id, self.test.id)
        self.assertEqual(assignment.category_id, self.category.id)
