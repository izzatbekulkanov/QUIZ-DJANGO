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
