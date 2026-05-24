from django.core.management.base import BaseCommand
from esg_platform.models import UnitConversion

class Command(BaseCommand):
    help = 'Seeds standard unit conversions'

    def handle(self, *args, **options):
        conversions = [
            {
                'from_unit': 'gallons',
                'to_unit': 'liters',
                'factor': 3.78541,
                'source': 'Standard Conversion',
            },
            {
                'from_unit': 'MWh',
                'to_unit': 'kWh',
                'factor': 1000.0,
                'source': 'Standard Conversion',
            },
            {
                'from_unit': 'short_ton',
                'to_unit': 'metric_ton',
                'factor': 0.907185,
                'source': 'Standard Conversion',
            },
            {
                'from_unit': 'miles',
                'to_unit': 'km',
                'factor': 1.60934,
                'source': 'Standard Conversion',
            },
        ]

        created_count = 0
        for conv in conversions:
            obj, created = UnitConversion.objects.update_or_create(
                from_unit=conv['from_unit'],
                to_unit=conv['to_unit'],
                defaults={
                    'factor': conv['factor'],
                    'source': conv['source'],
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} unit conversions.'))
