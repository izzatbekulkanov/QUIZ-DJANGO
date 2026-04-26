from django.test import TestCase
from django.urls import reverse

from apps.account.models import CustomUser
from apps.logs.models import Log


class LogsViewTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="logs-admin",
            password="secret123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)

    def test_logs_view_renders_for_admin(self):
        Log.objects.create(
            method="GET",
            path="/administrator/logs/",
            status_code=200,
            user=self.admin_user,
        )

        response = self.client.get(reverse("administrator:logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log yozuvlari")

    def test_clear_logs_view_deletes_all_rows(self):
        Log.objects.create(
            method="POST",
            path="/administrator/tests/",
            status_code=201,
            user=self.admin_user,
        )

        response = self.client.post(reverse("administrator:clear-logs"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"success": True, "message": "Barcha loglar muvaffaqiyatli o'chirildi!"},
        )
        self.assertEqual(Log.objects.count(), 0)
