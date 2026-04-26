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


class LogoutViewTests(TestCase):
    def test_logout_redirects_with_helper_logout_signal(self):
        user = CustomUser.objects.create_user(
            username="logout-user",
            password="secret123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("landing:logout"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("helper_logout=1", response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)


class OfficeHelperSessionStateViewTests(TestCase):
    def test_session_state_returns_not_authenticated_after_logout(self):
        response = self.client.get(reverse("landing:office-helper-session-state"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["authenticated"])

    def test_session_state_returns_current_session_payload(self):
        user = CustomUser.objects.create_user(
            username="helper-user",
            password="secret123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("landing:office-helper-session-state"))
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["session"]["username"], user.username)
        self.assertEqual(payload["session"]["expires_in_seconds"], 1800)
