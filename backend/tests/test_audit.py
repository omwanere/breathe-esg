import csv
import io
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from decimal import Decimal
from datetime import date
from django.utils import timezone
from apps.authentication.models import Tenant, User
from apps.ingestion.models import DataSource, IngestionJob, EmissionFactor
from apps.review.models import RawActivityRow
from apps.export.models import AuditLog
from apps.ingestion.parsers import ingest_sap_file

class AuditAndLogTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Tenant", slug="demo")
        self.user = User.objects.create_user(username="analyst@demo.com", password="password", tenant=self.tenant)
        self.ds = DataSource.objects.create(tenant=self.tenant, source_type="SAP_FUEL", ingestion_mode="FILE_UPLOAD")
        self.job = IngestionJob.objects.create(data_source=self.ds, status="COMPLETED")
        
        EmissionFactor.objects.create(
            activity_type="Diesel",
            region="UK",
            unit="liter",
            factor_kg_co2e_per_unit=Decimal("2.68"),
            source="DEFRA",
            valid_year=2023
        )

        # Create approved row
        self.row_approved = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="SAP_FUEL",
            scope="SCOPE_1",
            parsed_quantity=Decimal("100"),
            parsed_unit="liter",
            normalized_quantity_kg_co2e=Decimal("268.0"),
            activity_date=date(2024, 1, 15),
            status="APPROVED",
            is_locked=False
        )
        
        # Create pending row (should not be exported)
        self.row_pending = RawActivityRow.objects.create(
            tenant=self.tenant,
            ingestion_job=self.job,
            source_type="SAP_FUEL",
            scope="SCOPE_1",
            parsed_quantity=Decimal("50"),
            parsed_unit="liter",
            activity_date=date(2024, 1, 16),
            status="PENDING_REVIEW",
            is_locked=False
        )

    def authenticate(self):
        self.client.force_authenticate(user=self.user)

    def test_6_1_to_6_3_export_flow(self):
        self.authenticate()
        url = reverse('export_audit_ready')
        
        # 1. Export only approved rows
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        csv_data = response.content.decode('utf-8').splitlines()
        reader = csv.reader(csv_data)
        rows = list(reader)
        
        # Expect header row and 1 data row
        self.assertEqual(len(rows), 2)
        # Check header fields
        self.assertIn('id', rows[0])
        self.assertIn('scope', rows[0])
        self.assertIn('normalized_quantity_kg_co2e', rows[0])
        # Check data values
        self.assertEqual(rows[1][0], str(self.row_approved.id))
        self.assertEqual(rows[1][2], 'SCOPE_1')
        self.assertEqual(rows[1][9], '268.0000')

        # 2. Rows locked after export
        self.row_approved.refresh_from_db()
        self.assertTrue(self.row_approved.is_locked)
        
        # Verify LOCKED Audit Log was created
        lock_log = AuditLog.objects.filter(row=self.row_approved, action='LOCKED')
        self.assertTrue(lock_log.exists())
        self.assertEqual(lock_log.first().performed_by, self.user)

        # 3. Call export endpoint a second time -> CSV is empty of data rows (contains only headers)
        response_2 = self.client.get(url)
        self.assertEqual(response_2.status_code, status.HTTP_200_OK)
        csv_data_2 = response_2.content.decode('utf-8').splitlines()
        reader_2 = csv.reader(csv_data_2)
        rows_2 = list(reader_2)
        # Only header row
        self.assertEqual(len(rows_2), 1)

    def test_6_4_cannot_edit_locked_row(self):
        self.authenticate()
        
        # Lock row
        self.row_approved.is_locked = True
        self.row_approved.save()
        
        # Attempt to patch
        url = reverse('rawactivityrow-detail', kwargs={'pk': self.row_approved.id})
        response = self.client.patch(url, {'reviewer_note': 'Attempt to edit'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify row not modified
        self.row_approved.refresh_from_db()
        self.assertNotEqual(self.row_approved.reviewer_note, 'Attempt to edit')

    def test_7_1_to_7_3_audit_trail_events(self):
        self.authenticate()
        
        # 1. Create event logged (ingestion)
        # We simulate this by uploading a file via ingest_sap_file
        csv_content = (
            "Buchungsdatum,Werk,Material,Materialkurztext,Bewegungsart,Menge,Basismengeneinheit,Buchungsjahr,Buchungsperiode,Kostenstelle\n"
            "02.01.2024,1001,MAT-DI-01,Diesel fuel,261,100,L,2024,01,KST-5001\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        ingest_sap_file(self.job.id, file_obj, "sap.csv")
        
        # Inspect created rows and audit logs
        new_row = RawActivityRow.objects.get(ingestion_job=self.job, description="Diesel fuel")
        self.assertTrue(AuditLog.objects.filter(row=new_row, action='CREATED').exists())

        # 2. Edit event logged with diff
        url_edit = reverse('rawactivityrow-detail', kwargs={'pk': new_row.id})
        response = self.client.patch(url_edit, {'reviewer_note': 'Updated note'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        edit_log = AuditLog.objects.filter(row=new_row, action='EDITED')
        self.assertTrue(edit_log.exists())
        self.assertEqual(edit_log.first().before_state['reviewer_note'], None)
        self.assertEqual(edit_log.first().after_state['reviewer_note'], 'Updated note')

        # 3. Approve event logged
        url_approve = reverse('approve_row', kwargs={'pk': new_row.id})
        response_app = self.client.post(url_approve)
        self.assertEqual(response_app.status_code, status.HTTP_200_OK)
        
        app_log = AuditLog.objects.filter(row=new_row, action='APPROVED')
        self.assertTrue(app_log.exists())
        self.assertEqual(app_log.first().performed_by, self.user)
