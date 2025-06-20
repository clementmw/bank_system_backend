from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seeds the database with initial data'

    def handle(self, *args, **options):
        self.stdout.write("Seeding data...")
        pass
