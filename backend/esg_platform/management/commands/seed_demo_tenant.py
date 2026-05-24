from django.core.management.base import BaseCommand
from esg_platform.models import Tenant, User, DataSource

class Command(BaseCommand):
    help = 'Seeds the demo tenant, analyst user, and data sources'

    def handle(self, *args, **options):
        # Create Tenant
        tenant, created = Tenant.objects.get_or_create(
            slug='demo',
            defaults={'name': 'Demo Tenant'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created Demo Tenant"))
        else:
            self.stdout.write("Demo Tenant already exists")

        # Create Analyst User
        user, u_created = User.objects.get_or_create(
            username='analyst@demo.com',
            defaults={
                'email': 'analyst@demo.com',
                'tenant': tenant,
                'is_staff': True,
            }
        )
        if u_created:
            user.set_password('Demo1234!')
            user.save()
            self.stdout.write(self.style.SUCCESS("Created user analyst@demo.com with password Demo1234!"))
        else:
            self.stdout.write("User analyst@demo.com already exists")

        # Create standard Data Sources
        sources = [
            ('SAP_FUEL', 'FILE_UPLOAD'),
            ('SAP_PROCUREMENT', 'FILE_UPLOAD'),
            ('UTILITY_ELECTRICITY', 'FILE_UPLOAD'),
            ('TRAVEL_FLIGHT', 'FILE_UPLOAD'),
            ('TRAVEL_HOTEL', 'FILE_UPLOAD'),
            ('TRAVEL_GROUND', 'FILE_UPLOAD'),
        ]

        for s_type, mode in sources:
            ds, ds_created = DataSource.objects.get_or_create(
                tenant=tenant,
                source_type=s_type,
                defaults={'ingestion_mode': mode}
            )
            if ds_created:
                self.stdout.write(self.style.SUCCESS(f"Created DataSource {s_type}"))
            else:
                self.stdout.write(f"DataSource {s_type} already exists")

        self.stdout.write(self.style.SUCCESS("Seeding demo tenant process completed."))
