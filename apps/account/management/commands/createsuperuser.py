# account/management/commands/createsuperuser.py
from django.contrib.auth.management.commands.createsuperuser import Command as BaseCommand
from django.core.management import CommandError

class Command(BaseCommand):
    def handle(self, *args, **options):
        options['first_name'] = input('First name: ')
        options['second_name'] = input('Second name: ')

        if not options['first_name']:
            raise CommandError('First name is required.')
        if not options['second_name']:
            raise CommandError('Second name is required.')

        super().handle(*args, **options)