from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create master user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Master username', default='LCM_MC')
        parser.add_argument('--password', type=str, help='Master password', default='admin123')
        parser.add_argument('--email', type=str, help='Master email', default='liuchimo@outlook.com')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists')
            )
            return
            
        user = User.objects.create_superuser(
            username=username,
            password=password,
            email=email
        )
        user.role = 'master'
        user.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created master user "{username}"')
        )