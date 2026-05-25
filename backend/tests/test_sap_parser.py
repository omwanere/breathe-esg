from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import date
import io
from openpyxl import Workbook
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.authentication.models import Tenant, User
from apps.ingestion.models import DataSource, IngestionJob, UnitConversion, EmissionFactor
from apps.review.models import RawActivityRow
from apps.ingestion.parsers import ingest_sap_file, parse_german_decimal

class SAPParserTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Tenant", slug="demo")
        self.user = User.objects.create_user(username="analyst@demo.com", password="password", tenant=self.tenant)
        self.ds = DataSource.objects.create(
            tenant=self.tenant,
            source_type="SAP_FUEL",
            ingestion_mode="FILE_UPLOAD",
            config={"plant_mapping": {"1001": "Berlin Plant", "1002": "Munich Plant"}}
        )
        self.job = IngestionJob.objects.create(data_source=self.ds, status="PENDING", triggered_by=self.user)
        
        # Seed conversions and factors
        UnitConversion.objects.create(from_unit="gallons", to_unit="liters", factor=Decimal("3.78541"))
        EmissionFactor.objects.create(
            activity_type="Diesel",
            region="UK",
            unit="liter",
            factor_kg_co2e_per_unit=Decimal("2.68"),
            source="DEFRA",
            valid_year=2023
        )

    def test_2_1_happy_path(self):
        # Create CSV content
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "02.01.2024,1001,MAT-DI-01,Diesel fuel,261,1.500,L,2024,01,KST-5001\n"
            "03.01.2024,1002,MAT-ST-03,Steel plates,261,500,KG,2024,01,KST-5001\n"
            "04.01.2024,1001,MAT-ST-03,Steel ignored,311,500,KG,2024,01,KST-5001\n" # Excluded movement type
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        
        ingest_sap_file(self.job.id, file_obj, "sap_mb51_export.csv")
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "COMPLETED")
        self.assertEqual(self.job.row_count, 2)
        
        rows = RawActivityRow.objects.filter(ingestion_job=self.job)
        self.assertEqual(rows.count(), 2)
        
        # Check scope and fields
        diesel_row = rows.get(source_type="SAP_FUEL")
        self.assertEqual(diesel_row.tenant, self.tenant)
        self.assertEqual(diesel_row.scope, "SCOPE_1")
        self.assertEqual(diesel_row.parsed_quantity, Decimal("1.500"))
        self.assertEqual(diesel_row.parsed_unit, "liter")
        self.assertEqual(diesel_row.raw_data["Materialkurztext"], "Diesel fuel")
        
        steel_row = rows.get(source_type="SAP_PROCUREMENT")
        self.assertEqual(steel_row.scope, "SCOPE_3")
        self.assertEqual(steel_row.parsed_quantity, Decimal("500"))
        self.assertEqual(steel_row.parsed_unit, "kg")

    def test_2_2_german_decimal_format(self):
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "02.01.2024,1001,MAT-DI-01,Diesel fuel,261,\"1.234,56\",L,2024,01,KST-5001\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_sap_file(self.job.id, file_obj, "test.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.parsed_quantity, Decimal("1234.56"))

    def test_2_3_german_date_format(self):
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "15.03.2024,1001,MAT-DI-01,Diesel fuel,261,100,L,2024,01,KST-5001\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_sap_file(self.job.id, file_obj, "test.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.activity_date, date(2024, 3, 15))

    def test_2_4_unknown_unit_auto_flag(self):
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "02.01.2024,1001,MAT-DI-01,Diesel fuel,261,100,XYZ,2024,01,KST-5001\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_sap_file(self.job.id, file_obj, "test.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("Unrecognized unit" in r for r in row.flag_reasons))

    def test_2_5_negative_quantity_auto_flag(self):
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "02.01.2024,1001,MAT-DI-01,Diesel fuel,261,-500,L,2024,01,KST-5001\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_sap_file(self.job.id, file_obj, "test.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("Negative quantity" in r for r in row.flag_reasons))

    def test_2_6_missing_werk(self):
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "02.01.2024,,MAT-DI-01,Diesel fuel,261,100,L,2024,01,KST-5001\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_sap_file(self.job.id, file_obj, "test.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(any("Missing plant code" in r for r in row.flag_reasons))

    def test_2_7_xlsx_upload(self):
        wb = Workbook()
        ws = wb.active
        ws.append(['Buchungsdatum', 'Werk', 'Material', 'Materialkurztext', 'Bewegungsart', 'Menge', 'Basismengeneinheit', 'Buchungsjahr', 'Buchungsperiode', 'Kostenstelle'])
        ws.append(['02.01.2024', '1001', 'MAT-DI-01', 'Diesel fuel', '261', '1.234,56', 'L', '2024', '01', 'KST-5001'])
        
        file_obj = io.BytesIO()
        wb.save(file_obj)
        file_obj.seek(0)
        
        ingest_sap_file(self.job.id, file_obj, "sap_mb51.xlsx")
        
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "COMPLETED")
        self.assertEqual(self.job.row_count, 1)
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertEqual(row.parsed_quantity, Decimal("1234.56"))

    def test_2_8_encoding_resilience(self):
        # umlaut example in latin-1 (e.g. kraftstoff with potential special characters or material description)
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "02.01.2024,1001,MAT-DI-01,Diesel Kraftstoff mit Uml\xe4ut,261,100,L,2024,01,KST-5001\n"
        )
        file_obj = io.BytesIO(csv_content.encode("latin-1"))
        
        ingest_sap_file(self.job.id, file_obj, "test.csv")
        
        row = RawActivityRow.objects.get(ingestion_job=self.job)
        self.assertIn("mit Uml", row.description)

    def test_2_9_partial_failure_rollback(self):
        # We test partial failure rollback by mocking the generator to yield a valid row, then raise an exception.
        from apps.ingestion.views import run_async_ingestion
        from apps.ingestion import parsers
        
        original_read_file_data = parsers.read_file_data
        try:
            def mock_generator(*args, **kwargs):
                yield {
                    'Buchungsdatum': '02.01.2024',
                    'Werk': '1001',
                    'Material': 'MAT-DI-01',
                    'Materialkurztext': 'Diesel fuel',
                    'Bewegungsart': '261',
                    'Menge': '100',
                    'Basismengeneinheit': 'L',
                    'Buchungsjahr': '2024',
                    'Buchungsperiode': '01',
                    'Kostenstelle': 'KST-5001'
                }
                raise ValueError("Simulated parsing crash")
                
            parsers.read_file_data = mock_generator
            
            run_async_ingestion(ingest_sap_file, self.job.id, b"dummy", "test.csv")
                
            self.job.refresh_from_db()
            self.assertEqual(self.job.status, "FAILED")
            # Ensure database is empty of rows from this job
            self.assertEqual(RawActivityRow.objects.filter(ingestion_job=self.job).count(), 0)
        finally:
            parsers.read_file_data = original_read_file_data
