from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import date
from esg_platform.models import Tenant, User, DataSource, IngestionJob, RawActivityRow, UnitConversion, EmissionFactor
from esg_platform.parsers import parse_german_decimal, parse_standard_date, haversine_distance, calculate_emissions
import io

class ESGParserTests(TestCase):
    def setUp(self):
        # Create standard structures
        self.tenant = Tenant.objects.create(name='Test Tenant', slug='test')
        self.user = User.objects.create_user(username='test@test.com', password='testpassword', tenant=self.tenant)
        self.ds_sap = DataSource.objects.create(tenant=self.tenant, source_type='SAP_FUEL', ingestion_mode='FILE_UPLOAD')
        self.job = IngestionJob.objects.create(data_source=self.ds_sap, status='PENDING', triggered_by=self.user)
        
        # Seed unit conversions
        UnitConversion.objects.create(from_unit='gallons', to_unit='liters', factor=3.78541)
        UnitConversion.objects.create(from_unit='miles', to_unit='km', factor=1.60934)
        
        # Seed emission factors
        EmissionFactor.objects.create(activity_type='Diesel', region='UK', unit='liter', factor_kg_co2e_per_unit=2.68, source='DEFRA', valid_year=2023)
        EmissionFactor.objects.create(activity_type='Grid electricity UK average', region='UK', unit='kWh', factor_kg_co2e_per_unit=0.207, source='DEFRA', valid_year=2023)
        EmissionFactor.objects.create(activity_type='Short-haul flight', region='Global', unit='km', factor_kg_co2e_per_unit=0.255, source='DEFRA', valid_year=2023)

    def test_german_decimal_parsing(self):
        self.assertEqual(parse_german_decimal('1.234,56'), Decimal('1234.56'))
        self.assertEqual(parse_german_decimal('1234,56'), Decimal('1234.56'))
        self.assertEqual(parse_german_decimal('123'), Decimal('123'))
        self.assertEqual(parse_german_decimal('-12,50'), Decimal('-12.50'))

    def test_haversine_distance(self):
        # London (LHR) to New York (JFK)
        # LHR: 51.4700, -0.4543
        # JFK: 40.6398, -73.7789
        dist = haversine_distance(51.4700, -0.4543, 40.6398, -73.7789)
        # Expected distance is ~5570 km
        self.assertTrue(5500 < dist < 5600)

    def test_sap_emission_calculation_diesel(self):
        # Test diesel conversion and emission calculation
        row = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type='SAP_FUEL',
            scope='SCOPE_1',
            parsed_quantity=Decimal('100'),
            parsed_unit='liter',
            activity_date=date(2024, 2, 1),
            location='London Office',
            description='Diesel fuel usage',
            status='PENDING_REVIEW'
        )

        kwh, co2e, ef_used, ef_src, flags = calculate_emissions(row)
        self.assertIsNone(kwh)
        self.assertEqual(co2e, Decimal('268.00')) # 100 * 2.68
        self.assertEqual(ef_used, Decimal('2.68'))
        self.assertEqual(ef_src, 'DEFRA 2023')
        self.assertEqual(len(flags), 0)

    def test_sap_emission_calculation_diesel_gallons(self):
        # Test diesel in gallons
        row = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type='SAP_FUEL',
            scope='SCOPE_1',
            parsed_quantity=Decimal('10'),
            parsed_unit='gallons',
            activity_date=date(2024, 2, 1),
            location='London Office',
            description='Diesel fuel usage in gallons',
            status='PENDING_REVIEW'
        )

        kwh, co2e, ef_used, ef_src, flags = calculate_emissions(row)
        # 10 gallons = 37.8541 liters. 37.8541 * 2.68 = 101.448988 kg
        self.assertAlmostEqual(co2e, Decimal('101.448988'))
        self.assertEqual(ef_used, Decimal('2.68'))

    def test_utility_electricity_calculation(self):
        row = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type='UTILITY_ELECTRICITY',
            scope='SCOPE_2',
            parsed_quantity=Decimal('500'),
            parsed_unit='kWh',
            activity_date=date(2023, 6, 1),
            location='London Factory UK',
            description='Grid electricity bill',
            status='PENDING_REVIEW'
        )

        kwh, co2e, ef_used, ef_src, flags = calculate_emissions(row)
        self.assertEqual(kwh, Decimal('500'))
        self.assertEqual(co2e, Decimal('103.500')) # 500 * 0.207 (UK grid average)
        self.assertEqual(ef_used, Decimal('0.207'))
        self.assertEqual(ef_src, 'DEFRA 2023')
