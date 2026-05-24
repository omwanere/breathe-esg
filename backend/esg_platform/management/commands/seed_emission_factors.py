from django.core.management.base import BaseCommand
from esg_platform.models import EmissionFactor

class Command(BaseCommand):
    help = 'Seeds ESG emission factors'

    def handle(self, *args, **options):
        factors = [
            {
                'activity_type': 'Diesel',
                'region': 'UK',
                'unit': 'liter',
                'factor_kg_co2e_per_unit': 2.68,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
            {
                'activity_type': 'Grid electricity UK average',
                'region': 'UK',
                'unit': 'kWh',
                'factor_kg_co2e_per_unit': 0.207,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
            {
                'activity_type': 'Grid electricity US average',
                'region': 'US',
                'unit': 'kWh',
                'factor_kg_co2e_per_unit': 0.386,
                'source': 'EPA',
                'valid_year': 2022,
            },
            {
                'activity_type': 'Short-haul flight',
                'region': 'Global',
                'unit': 'km',
                'factor_kg_co2e_per_unit': 0.255,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
            {
                'activity_type': 'Long-haul flight',
                'region': 'Global',
                'unit': 'km',
                'factor_kg_co2e_per_unit': 0.195,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
            {
                'activity_type': 'Hotel stay',
                'region': 'Global',
                'unit': 'room-night',
                'factor_kg_co2e_per_unit': 31.9,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
            {
                'activity_type': 'Car Rental',
                'region': 'Global',
                'unit': 'km',
                'factor_kg_co2e_per_unit': 0.192,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
            {
                'activity_type': 'Rail',
                'region': 'Global',
                'unit': 'km',
                'factor_kg_co2e_per_unit': 0.035,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
            {
                'activity_type': 'Taxi',
                'region': 'Global',
                'unit': 'km',
                'factor_kg_co2e_per_unit': 0.149,
                'source': 'DEFRA',
                'valid_year': 2023,
            },
        ]

        created_count = 0
        for fact in factors:
            obj, created = EmissionFactor.objects.update_or_create(
                activity_type=fact['activity_type'],
                region=fact['region'],
                unit=fact['unit'],
                valid_year=fact['valid_year'],
                defaults={
                    'factor_kg_co2e_per_unit': fact['factor_kg_co2e_per_unit'],
                    'source': fact['source'],
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} emission factors.'))
