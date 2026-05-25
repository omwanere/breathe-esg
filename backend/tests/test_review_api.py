from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from decimal import Decimal
from datetime import date
from django.utils import timezone
from esg_platform.models import Tenant, User, DataSource, IngestionJob, RawActivityRow, AuditLog, EmissionFactor

class ReviewAPITests(APITestCase):
    def setUp(self):
        # Create Tenants
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a")
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b")
        
        # Create Users
        self.user_a = User.objects.create_user(username="analyst@tenant-a.com", password="password", tenant=self.tenant_a)
        self.user_b = User.objects.create_user(username="analyst@tenant-b.com", password="password", tenant=self.tenant_b)
        
        # Data Sources
        self.ds_a = DataSource.objects.create(tenant=self.tenant_a, source_type="SAP_FUEL", ingestion_mode="FILE_UPLOAD")
        self.ds_b = DataSource.objects.create(tenant=self.tenant_b, source_type="SAP_FUEL", ingestion_mode="FILE_UPLOAD")
        
        # Jobs
        self.job_a = IngestionJob.objects.create(data_source=self.ds_a, status="COMPLETED")
        self.job_b = IngestionJob.objects.create(data_source=self.ds_b, status="COMPLETED")
        
        # Seed conversion/emission factors for calculations
        EmissionFactor.objects.get_or_create(
            activity_type="Diesel",
            region="UK",
            unit="liter",
            defaults={"factor_kg_co2e_per_unit": Decimal("2.68"), "source": "DEFRA", "valid_year": 2023}
        )

        # Create rows for Tenant A
        self.row_pending = RawActivityRow.objects.create(
            tenant=self.tenant_a,
            ingestion_job=self.job_a,
            source_type="SAP_FUEL",
            scope="SCOPE_1",
            parsed_quantity=Decimal("100"),
            parsed_unit="liter",
            activity_date=date(2024, 1, 15),
            location="Berlin Plant",
            description="Diesel fuel usage",
            status="PENDING_REVIEW"
        )
        self.row_flagged = RawActivityRow.objects.create(
            tenant=self.tenant_a,
            ingestion_job=self.job_a,
            source_type="UTILITY_ELECTRICITY",
            scope="SCOPE_2",
            parsed_quantity=Decimal("0"),
            parsed_unit="kWh",
            activity_date=date(2024, 1, 20),
            location="London Plant",
            description="Grid electricity",
            status="FLAGGED"
        )
        
        # Create rows for Tenant B
        self.row_tenant_b = RawActivityRow.objects.create(
            tenant=self.tenant_b,
            ingestion_job=self.job_b,
            source_type="SAP_FUEL",
            scope="SCOPE_1",
            parsed_quantity=Decimal("200"),
            parsed_unit="liter",
            activity_date=date(2024, 2, 10),
            status="PENDING_REVIEW"
        )

    def authenticate_user_a(self):
        self.client.force_authenticate(user=self.user_a)

    def test_5_1_row_listing_with_pagination(self):
        self.authenticate_user_a()
        url = reverse('rawactivityrow-list')
        response = self.client.get(url, {'page': 1, 'page_size': 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertIn('next', response.data)

    def test_5_2_filter_by_status(self):
        self.authenticate_user_a()
        url = reverse('rawactivityrow-list')
        response = self.client.get(url, {'status': 'FLAGGED'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'FLAGGED')

    def test_5_3_filter_by_source_type(self):
        self.authenticate_user_a()
        url = reverse('rawactivityrow-list')
        response = self.client.get(url, {'source_type': 'SAP_FUEL'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_type'], 'SAP_FUEL')

    def test_5_4_filter_by_scope(self):
        self.authenticate_user_a()
        url = reverse('rawactivityrow-list')
        response = self.client.get(url, {'scope': 'SCOPE_2'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['scope'], 'SCOPE_2')

    def test_5_5_filter_by_date_range(self):
        self.authenticate_user_a()
        url = reverse('rawactivityrow-list')
        
        # Test date_from and date_to compatibility catch
        response = self.client.get(url, {'date_from': '2024-01-01', 'date_to': '2024-01-31'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 2) # Both rows are in January 2024

    def test_5_6_single_row_approve(self):
        self.authenticate_user_a()
        url = reverse('approve_row', kwargs={'pk': self.row_pending.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.row_pending.refresh_from_db()
        self.assertEqual(self.row_pending.status, 'APPROVED')
        self.assertEqual(self.row_pending.reviewed_by, self.user_a)
        self.assertIsNotNone(self.row_pending.reviewed_at)
        self.assertFalse(self.row_pending.is_locked)
        
        # Verify Audit Log
        audit_log = AuditLog.objects.filter(row=self.row_pending, action='APPROVED')
        self.assertTrue(audit_log.exists())
        self.assertEqual(audit_log.first().performed_by, self.user_a)

    def test_5_7_single_row_reject(self):
        self.authenticate_user_a()
        url = reverse('reject_row', kwargs={'pk': self.row_pending.id})
        
        # Reject without note returns 400
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Reject with note works
        response = self.client.post(url, {'reviewer_note': 'Duplicate entry'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.row_pending.refresh_from_db()
        self.assertEqual(self.row_pending.status, 'REJECTED')
        self.assertEqual(self.row_pending.reviewer_note, 'Duplicate entry')

    def test_5_8_bulk_approve(self):
        self.authenticate_user_a()
        url = reverse('bulk_approve')
        
        # Let's create another pending row
        row_pending_2 = RawActivityRow.objects.create(
            tenant=self.tenant_a,
            ingestion_job=self.job_a,
            source_type="SAP_FUEL",
            scope="SCOPE_1",
            parsed_quantity=Decimal("50"),
            parsed_unit="liter",
            activity_date=date(2024, 1, 15),
            status="PENDING_REVIEW"
        )
        
        ids = [str(self.row_pending.id), str(row_pending_2.id)]
        response = self.client.post(url, {'ids': ids}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.row_pending.refresh_from_db()
        row_pending_2.refresh_from_db()
        self.assertEqual(self.row_pending.status, 'APPROVED')
        self.assertEqual(row_pending_2.status, 'APPROVED')
        
        # Audit Logs check
        self.assertTrue(AuditLog.objects.filter(row=self.row_pending, action='APPROVED').exists())
        self.assertTrue(AuditLog.objects.filter(row=row_pending_2, action='APPROVED').exists())

    def test_5_9_cannot_approve_already_locked_row(self):
        self.authenticate_user_a()
        
        # Manually lock row
        self.row_pending.is_locked = True
        self.row_pending.save()
        
        url = reverse('approve_row', kwargs={'pk': self.row_pending.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_5_10_summary_endpoint(self):
        self.authenticate_user_a()
        url = reverse('review_summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pending_review'], 1)
        self.assertEqual(response.data['flagged'], 1)
        self.assertEqual(response.data['scopes']['SCOPE_1'], 1)
        self.assertEqual(response.data['scopes']['SCOPE_2'], 1)

    def test_5_11_tenant_isolation(self):
        # Log in as Tenant A
        self.authenticate_user_a()
        
        # GET rows -> only Tenant A rows returned (2 rows), Tenant B row excluded
        url_list = reverse('rawactivityrow-list')
        response = self.client.get(url_list)
        results = response.data['results']
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertNotEqual(r['id'], str(self.row_tenant_b.id))
            
        # Attempt to approve Tenant B row directly -> should return 404
        url_approve = reverse('approve_row', kwargs={'pk': self.row_tenant_b.id})
        response = self.client.post(url_approve)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
