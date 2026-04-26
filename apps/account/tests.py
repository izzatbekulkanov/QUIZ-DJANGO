from django.test import TestCase
from django.urls import reverse

from apps.account.models import CustomUser


class IdLoginViewTests(TestCase):
    def test_id_login_accepts_13_digit_username(self):
        user = CustomUser.objects.create_user(
            username="4440123456807",
            password="namdpi451",
            auth_is_id=True,
            is_student=True,
        )

        response = self.client.post(
            reverse("landing:id_login"),
            {"id_number": "4440123456807"},
        )

        self.assertRedirects(response, reverse("landing:two_login"))
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))


class CheckUsernameViewTests(TestCase):
    def setUp(self):
        self.current_user = CustomUser.objects.create_user(
            username="current-user",
            password="secret123",
        )
        self.other_user = CustomUser.objects.create_user(
            username="taken-user",
            password="secret123",
        )

    def test_check_username_ignores_current_user_when_excluded(self):
        response = self.client.get(
            reverse("landing:check-username"),
            {
                "username": self.current_user.username,
                "exclude_user_id": self.current_user.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_taken"])

    def test_check_username_flags_another_existing_user(self):
        response = self.client.get(
            reverse("landing:check-username"),
            {
                "username": self.other_user.username,
                "exclude_user_id": self.current_user.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_taken"])
