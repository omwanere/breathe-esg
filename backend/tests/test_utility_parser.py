from django.test import TestCase
from decimal import Decimal
from datetime import date
import io
from apps.authentication.models import Tenant, User
from apps.ingestion.models import DataSource, IngestionJob, UnitConversion, EmissionFactor
from apps.review.models import RawActivityRow
from apps.ingestion.parsers import ingest_utility_file, calculate_emissions

class UtilityParserTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Tenant", slug="demo")
        self.user = User.objects.create_user(username="analyst@demo.com", password="password", tenant=self.tenant)
        self.ds = DataSource.objects.create(
            tenant=self.tenant,
            source_type="UTILITY_ELECTRICITY",
            ingestion_mode="FILE_UPLOAD"
        )
        self.job = IngestionJob.objects.create(data_source=self.ds, status="PENDING", triggered_by=self.user)
        
        # Seed conversions and factors
        UnitConversion.objects.get_or_create(from_unit="MWh", to_unit="kWh", defaults={"factor": Decimal("1000.0")})
        
        EmissionFactor.objects.create(
            activity_type="Grid electricity UK average",
            region="UK",
            unit="kWh",
            factor_kg_co2e_per_unit=Decimal("0.207"),
            source="DEFRA",
            valid_year=2023
        )
        EmissionFactor.objects.create(
            activity_type="Grid electricity US average",
            region="US",
            unit="kWh",
            factor_kg_co2e_per_unit=Decimal("0.386"),
            source="EPA",
            valid_year=2022
        )

    def test_3_1_happy_path(self):
        csv_content = (
            "account_number,meter_id,site_name,site_address,billing_period_start,billing_period_end,consumption_kwh,consumption_unit,demand_kw,tariff_code,supplier_name,invoice_number,invoice_date\n"
            "AC-123,METER-01,Berlin Plant,Berlin,2024-01-01,2024-01-31,500,kWh,10,T-1,Vattenfall,INV-1,2024-02-05\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        
        ingest_utility_file(self.job.id, file_obj, "utility.csv")
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "COMPLETED")
        self.assertEqual(self.job.row_count, 1)
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.scope, "SCOPE_2")
        self.assertEqual(row.period_start, date(2024, 1, 1))
        self.assertEqual(row.period_end, date(2024, 1, 31))
        # Midpoint of 30 days is 15 days -> Jan 16
        self.assertEqual(row.activity_date, date(2024, 1, 16))

    def test_3_2_mwh_normalization(self):
        csv_content = (
            "account_number,meter_id,site_name,site_address,billing_period_start,billing_period_end,consumption_kwh,consumption_unit,demand_kw,tariff_code,supplier_name,invoice_number,invoice_date\n"
            "AC-123,METER-01,Berlin Plant,Berlin,2024-01-01,2024-01-31,1.5,MWh,10,T-1,Vattenfall,INV-1,2024-02-05\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_utility_file(self.job.id, file_obj, "utility.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.normalized_quantity_kwh, Decimal("1500.0"))

    def test_3_3_kwh_passthrough(self):
        csv_content = (
            "account_number,meter_id,site_name,site_address,billing_period_start,billing_period_end,consumption_kwh,consumption_unit,demand_kw,tariff_code,supplier_name,invoice_number,invoice_date\n"
            "AC-123,METER-01,Berlin Plant,Berlin,2024-01-01,2024-01-31,500,kWh,10,T-1,Vattenfall,INV-1,2024-02-05\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_utility_file(self.job.id, file_obj, "utility.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.normalized_quantity_kwh, Decimal("500"))

    def test_3_4_long_billing_period_flag(self):
        csv_content = (
            "account_number,meter_id,site_name,site_address,billing_period_start,billing_period_end,consumption_kwh,consumption_unit,demand_kw,tariff_code,supplier_name,invoice_number,invoice_date\n"
            "AC-123,METER-01,Berlin Plant,Berlin,2024-01-01,2024-02-15,500,kWh,10,T-1,Vattenfall,INV-1,2024-02-20\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_utility_file(self.job.id, file_obj, "utility.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("Billing period length" in r for r in row.flag_reasons))

    def test_3_5_zero_consumption_flag(self):
        csv_content = (
            "account_number,meter_id,site_name,site_address,billing_period_start,billing_period_end,consumption_kwh,consumption_unit,demand_kw,tariff_code,supplier_name,invoice_number,invoice_date\n"
            "AC-123,METER-01,Berlin Plant,Berlin,2024-01-01,2024-01-30,0,kWh,10,T-1,Vattenfall,INV-1,2024-02-05\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_utility_file(self.job.id, file_obj, "utility.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("Zero energy consumption" in r for r in row.flag_reasons))

    def test_3_6_month_boundaries_preservation(self):
        csv_content = (
            "account_number,meter_id,site_name,site_address,billing_period_start,billing_period_end,consumption_kwh,consumption_unit,demand_kw,tariff_code,supplier_name,invoice_number,invoice_date\n"
            "AC-123,METER-01,Berlin Plant,Berlin,2024-01-14,2024-02-13,500,kWh,10,T-1,Vattenfall,INV-1,2024-02-20\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_utility_file(self.job.id, file_obj, "utility.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.period_start, date(2024, 1, 14))
        self.assertEqual(row.period_end, date(2024, 2, 13))

    def test_3_7_region_based_ef_selection(self):
        # Create a UK row
        row_uk = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="UTILITY_ELECTRICITY",
            scope="SCOPE_2",
            parsed_quantity=Decimal("100"),
            parsed_unit="kWh",
            activity_date=date(2024, 1, 1),
            location="Berlin Plant UK",
            description="UK grid electricity"
        )
        # Create a US row
        row_us = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="UTILITY_ELECTRICITY",
            scope="SCOPE_2",
            parsed_quantity=Decimal("100"),
            parsed_unit="kWh",
            activity_date=date(2024, 1, 1),
            location="US-WECC warehouse",
            description="US grid electricity"
        )
        
        # Calculate for UK
        kwh_uk, co2e_uk, ef_uk, src_uk, flags_uk = calculate_emissions(row_uk)
        self.assertEqual(ef_uk, Decimal("0.207"))
        self.assertEqual(co2e_uk, Decimal("20.7"))
        
        # Calculate for US
        kwh_us, co2e_us, ef_us, src_us, flags_us = calculate_emissions(row_us)
        self.assertEqual(ef_us, Decimal("0.386"))
        self.assertEqual(co2e_us, Decimal("38.6"))

    def test_3_8_missing_account_number(self):
        csv_content = (
            "account_number,meter_id,site_name,site_address,billing_period_start,billing_period_end,consumption_kwh,consumption_unit,demand_kw,tariff_code,supplier_name,invoice_number,invoice_date\n"
            ",METER-01,Berlin Plant,Berlin,2024-01-01,2024-01-30,500,kWh,10,T-1,Vattenfall,INV-1,2024-02-05\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_utility_file(self.job.id, file_obj, "utility.csv")
        
        # Ingest succeeds and is not crashed
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "COMPLETED")
