from django.test import TestCase
from decimal import Decimal
from datetime import date
from apps.authentication.models import Tenant
from apps.ingestion.models import DataSource, IngestionJob, UnitConversion, EmissionFactor
from apps.review.models import RawActivityRow
from apps.ingestion.parsers import parse_german_decimal, haversine_distance, calculate_emissions

class ESGParserTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Tenant", slug="demo")
        self.ds_sap = DataSource.objects.create(tenant=self.tenant, source_type="SAP_FUEL", ingestion_mode="FILE_UPLOAD")
        self.ds_utility = DataSource.objects.create(tenant=self.tenant, source_type="UTILITY_ELECTRICITY", ingestion_mode="FILE_UPLOAD")
        
        self.job_sap = IngestionJob.objects.create(data_source=self.ds_sap, status="COMPLETED")
        self.job_utility = IngestionJob.objects.create(data_source=self.ds_utility, status="COMPLETED")
        
        # Seed conversions and factors
        UnitConversion.objects.get_or_create(from_unit="gallons", to_unit="liters", defaults={"factor": Decimal("3.78541")})
        UnitConversion.objects.get_or_create(from_unit="MWh", to_unit="kWh", defaults={"factor": Decimal("1000.0")})
        
        EmissionFactor.objects.get_or_create(
            activity_type="Diesel",
            region="UK",
            unit="liter",
            defaults={"factor_kg_co2e_per_unit": Decimal("2.68"), "source": "DEFRA", "valid_year": 2023}
        )
        EmissionFactor.objects.get_or_create(
            activity_type="Grid electricity UK average",
            region="UK",
            unit="kWh",
            defaults={"factor_kg_co2e_per_unit": Decimal("0.207"), "source": "DEFRA", "valid_year": 2023}
        )
        EmissionFactor.objects.get_or_create(
            activity_type="Grid electricity US average",
            region="US",
            unit="kWh",
            defaults={"factor_kg_co2e_per_unit": Decimal("0.386"), "source": "EPA", "valid_year": 2022}
        )

    def test_german_decimal_parsing(self):
        self.assertEqual(parse_german_decimal("1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_german_decimal("123,45"), Decimal("123.45"))
        self.assertEqual(parse_german_decimal("1000"), Decimal("1000"))

    def test_haversine_distance(self):
        # LHR coordinates: 51.4700, -0.4543
        # JFK coordinates: 40.6398, -73.7789
        distance = haversine_distance(51.4700, -0.4543, 40.6398, -73.7789)
        self.assertTrue(abs(distance - 5540) < 100) # within 100 km of 5540

    def test_sap_emission_calculation_diesel(self):
        row = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job_sap,
            source_type="SAP_FUEL",
            scope="SCOPE_1",
            parsed_quantity=Decimal("1000"),
            parsed_unit="liter",
            activity_date=date(2024, 1, 1),
            description="Diesel fuel usage"
        )
        kwh, co2e, ef, src, flags = calculate_emissions(row)
        self.assertIsNone(kwh)
        self.assertEqual(co2e, Decimal("2680.00")) # 1000 * 2.68
        self.assertEqual(ef, Decimal("2.68"))

    def test_sap_emission_calculation_diesel_gallons(self):
        row = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job_sap,
            source_type="SAP_FUEL",
            scope="SCOPE_1",
            parsed_quantity=Decimal("100"),
            parsed_unit="gallons",
            activity_date=date(2024, 1, 1),
            description="Diesel fuel usage"
        )
        kwh, co2e, ef, src, flags = calculate_emissions(row)
        self.assertIsNone(kwh)
        # 100 gallons * 3.78541 = 378.541 liters -> 378.541 * 2.68 = 1014.48988 kg CO2e
        self.assertAlmostEqual(co2e, Decimal("1014.48988"))

    def test_utility_electricity_calculation(self):
        # US electricity
        row_us = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job_utility,
            source_type="UTILITY_ELECTRICITY",
            scope="SCOPE_2",
            parsed_quantity=Decimal("1000"),
            parsed_unit="kWh",
            activity_date=date(2024, 1, 1),
            location="US East site",
            description="Grid electricity usage"
        )
        kwh, co2e_us, ef_us, src, flags = calculate_emissions(row_us)
        self.assertEqual(co2e_us, Decimal("386.0")) # 1000 * 0.386
        
        # UK electricity
        row_uk = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job_utility,
            source_type="UTILITY_ELECTRICITY",
            scope="SCOPE_2",
            parsed_quantity=Decimal("1000"),
            parsed_unit="kWh",
            activity_date=date(2024, 1, 1),
            location="UK site",
            description="Grid electricity UK average"
        )
        kwh, co2e_uk, ef_uk, src, flags = calculate_emissions(row_uk)
        self.assertEqual(co2e_uk, Decimal("207.0")) # 1000 * 0.207
