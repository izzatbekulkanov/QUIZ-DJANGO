import csv
from django.core.management.base import BaseCommand
from account.models import CustomUser

class Command(BaseCommand):
    help = 'Export users to a CSV file'

    def handle(self, *args, **kwargs):
        with open('users_export.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Username', 'Email', 'Full Name', 'Date Joined'])

            for user in CustomUser.objects.all():
                writer.writerow([user.username, user.email, user.full_name, user.date_joined])

        self.stdout.write(self.style.SUCCESS('User data exported successfully!'))