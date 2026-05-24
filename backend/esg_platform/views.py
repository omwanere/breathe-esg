import csv
import threading
from datetime import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from esg_platform.models import (
    Tenant, User, DataSource, IngestionJob, RawActivityRow, AuditLog, UnitConversion, EmissionFactor
)
from esg_platform.serializers import (
    DataSourceSerializer, IngestionJobSerializer, RawActivityRowSerializer, UserSerializer
)
from esg_platform.parsers import (
    ingest_sap_file, ingest_utility_file, ingest_travel_file, calculate_emissions
)

# Custom JWT Views to return user details
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user_serializer = UserSerializer(self.user)
        data['user'] = user_serializer.data
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# Base ViewSet to enforce tenant scoping
class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Enforce tenant isolation
        user = self.request.user
        if not user.tenant:
            return self.queryset.none()
        return self.queryset.filter(tenant=user.tenant)


# DataSource views
class DataSourceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.tenant:
            return DataSource.objects.none()
        return DataSource.objects.filter(tenant=user.tenant)


# Ingestion Job views
class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = IngestionJobSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.tenant:
            return IngestionJob.objects.none()
        return IngestionJob.objects.filter(data_source__tenant=user.tenant).order_by('-started_at')


# Async execution runner (simulates Celery queue using native threading)
def run_async_ingestion(parser_func, job_id, file_content, filename):
    file_obj = io_bytes = io_bytes = None
    try:
        import io
        file_obj = io.BytesIO(file_content)
        parser_func(job_id, file_obj, filename)
    except Exception as e:
        # Fallback if unhandled error propagates outside parser
        try:
            job = IngestionJob.objects.get(id=job_id)
            job.status = 'FAILED'
            job.error_log.append({'error': str(e), 'step': 'Background processing'})
            job.save()
        except:
            pass


# Upload Views
class BaseUploadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_data_source(self, source_type):
        user = self.request.user
        ds = DataSource.objects.filter(tenant=user.tenant, source_type=source_type).first()
        if not ds:
            # Auto-create data source for tenant if missing
            ds = DataSource.objects.create(tenant=user.tenant, source_type=source_type, ingestion_mode='FILE_UPLOAD')
        return ds

    def handle_upload(self, request, source_type, parser_func):
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded', 'detail': 'Key name should be "file"'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        ds = self.get_data_source(source_type)
        
        # Create IngestionJob
        job = IngestionJob.objects.create(
            data_source=ds,
            status='PENDING',
            raw_file=uploaded_file,
            triggered_by=request.user
        )

        # Read file contents and launch parser in a background thread to prevent API blocking
        file_content = uploaded_file.read()
        filename = uploaded_file.name

        threading.Thread(
            target=run_async_ingestion,
            args=(parser_func, job.id, file_content, filename)
        ).start()

        serializer = IngestionJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class UploadSAPView(BaseUploadView):
    def post(self, request):
        # We classify the primary type based on the file content or upload details, 
        # but both fall under the SAP ingestion pipeline. We'll default to SAP_FUEL.
        return self.handle_upload(request, 'SAP_FUEL', ingest_sap_file)

class UploadUtilityView(BaseUploadView):
    def post(self, request):
        return self.handle_upload(request, 'UTILITY_ELECTRICITY', ingest_utility_file)

class UploadTravelView(BaseUploadView):
    def post(self, request):
        # Default to TRAVEL_FLIGHT since it covers flight, hotel, and ground
        return self.handle_upload(request, 'TRAVEL_FLIGHT', ingest_travel_file)


# Review Dashboard pagination (50 rows/page)
class ReviewRowPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


# Review Dashboard views
class RawActivityRowViewSet(TenantScopedViewSet):
    serializer_class = RawActivityRowSerializer
    pagination_class = ReviewRowPagination
    queryset = RawActivityRow.objects.all().order_by('-activity_date')

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filter parameters
        status_param = self.request.query_params.get('status')
        source_param = self.request.query_params.get('source_type')
        scope_param = self.request.query_params.get('scope')
        flagged_only = self.request.query_params.get('flagged_only')
        
        date_start = self.request.query_params.get('date_start')
        date_end = self.request.query_params.get('date_end')

        if status_param:
            qs = qs.filter(status=status_param)
        if source_param:
            qs = qs.filter(source_type=source_param)
        if scope_param:
            qs = qs.filter(scope=scope_param)
        if flagged_only == 'true':
            qs = qs.filter(status='FLAGGED')
            
        if date_start:
            try:
                qs = qs.filter(activity_date__gte=datetime.strptime(date_start, '%Y-%m-%d').date())
            except ValueError:
                pass
        if date_end:
            try:
                qs = qs.filter(activity_date__lte=datetime.strptime(date_end, '%Y-%m-%d').date())
            except ValueError:
                pass

        return qs

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        # Custom patch logic to capture modifications in audit logs
        row = self.get_object()
        if row.is_locked:
            return Response({'error': 'Locked row', 'detail': 'This row has been exported and locked, and cannot be edited.'}, status=status.HTTP_400_BAD_REQUEST)
        
        before_state = {
            'parsed_quantity': str(row.parsed_quantity),
            'parsed_unit': row.parsed_unit,
            'location': row.location,
            'description': row.description,
            'status': row.status,
            'reviewer_note': row.reviewer_note,
        }

        # Check if quantity or unit is being changed
        qty_change = 'parsed_quantity' in request.data and Decimal(str(request.data['parsed_quantity'])) != row.parsed_quantity
        unit_change = 'parsed_unit' in request.data and request.data['parsed_unit'] != row.parsed_unit
        
        serializer = self.get_serializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Reload row from DB
        row.refresh_from_db()

        # If quantity or unit was changed, set edited_from_raw = True and re-run flag checks/calculations
        if qty_change or unit_change:
            row.edited_from_raw = True
            
            # Recalculate flag status
            flags = []
            if row.parsed_quantity < 0:
                flags.append("Negative quantity detected")
            if row.source_type == 'UTILITY_ELECTRICITY' and row.parsed_quantity == 0:
                flags.append("Zero energy consumption reported")
            
            # Standardize unit check
            valid_units = ['liter', 'gallons', 'kg', 'pieces', 'MWh', 'kWh', 'miles', 'km', 'room-night']
            if row.parsed_unit not in valid_units:
                flags.append(f"Unrecognized unit: {row.parsed_unit}")

            row.flag_reasons = flags
            if flags:
                row.status = 'FLAGGED'
            elif row.status == 'FLAGGED':
                row.status = 'PENDING_REVIEW'
            
            row.save()

        # Capture audit log
        after_state = {
            'parsed_quantity': str(row.parsed_quantity),
            'parsed_unit': row.parsed_unit,
            'location': row.location,
            'description': row.description,
            'status': row.status,
            'reviewer_note': row.reviewer_note,
        }

        AuditLog.objects.create(
            tenant=row.tenant,
            row=row,
            action='EDITED',
            performed_by=request.user,
            before_state=before_state,
            after_state=after_state
        )

        return Response(self.get_serializer(row).data)


# Single row actions (approve / reject)
class ApproveRowView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            row = RawActivityRow.objects.get(pk=pk, tenant=request.user.tenant)
        except RawActivityRow.DoesNotExist:
            return Response({'error': 'Row not found', 'detail': 'The specified row does not exist for this tenant.'}, status=status.HTTP_404_NOT_FOUND)
        
        if row.is_locked:
            return Response({'error': 'Locked row', 'detail': 'This row has been locked for audit and cannot be modified.'}, status=status.HTTP_400_BAD_REQUEST)

        before_state = {'status': row.status}

        # Perform ESG Normalization Calculations
        kwh, co2e, ef_used, ef_src, flags = calculate_emissions(row)
        
        # Apply calculations
        row.normalized_quantity_kwh = kwh
        row.normalized_quantity_kg_co2e = co2e
        row.emission_factor_used = ef_used
        row.emission_factor_source = ef_src
        row.flag_reasons = flags
        
        row.status = 'APPROVED'
        row.reviewed_by = request.user
        row.reviewed_at = timezone.now()
        if 'reviewer_note' in request.data:
            row.reviewer_note = request.data['reviewer_note']
        
        row.save()

        # Log to audit trail
        AuditLog.objects.create(
            tenant=row.tenant,
            row=row,
            action='APPROVED',
            performed_by=request.user,
            before_state=before_state,
            after_state={
                'status': row.status,
                'normalized_quantity_kg_co2e': str(row.normalized_quantity_kg_co2e),
                'emission_factor_used': str(row.emission_factor_used)
            }
        )

        return Response(RawActivityRowSerializer(row).data)

class RejectRowView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            row = RawActivityRow.objects.get(pk=pk, tenant=request.user.tenant)
        except RawActivityRow.DoesNotExist:
            return Response({'error': 'Row not found', 'detail': 'The specified row does not exist for this tenant.'}, status=status.HTTP_404_NOT_FOUND)
        
        if row.is_locked:
            return Response({'error': 'Locked row', 'detail': 'This row is locked for audit.'}, status=status.HTTP_400_BAD_REQUEST)

        reviewer_note = request.data.get('reviewer_note', '').strip()
        if not reviewer_note:
            return Response({'error': 'Note required', 'detail': 'A reviewer note is required to reject a row.'}, status=status.HTTP_400_BAD_REQUEST)

        before_state = {'status': row.status}

        row.status = 'REJECTED'
        row.reviewed_by = request.user
        row.reviewed_at = timezone.now()
        row.reviewer_note = reviewer_note
        row.save()

        # Log audit trail
        AuditLog.objects.create(
            tenant=row.tenant,
            row=row,
            action='REJECTED',
            performed_by=request.user,
            before_state=before_state,
            after_state={'status': row.status, 'reviewer_note': reviewer_note}
        )

        return Response(RawActivityRowSerializer(row).data)


# Bulk approve endpoint
class BulkApproveRowsView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        row_ids = request.data.get('ids', [])
        if not row_ids:
            return Response({'error': 'IDs required', 'detail': 'A list of row IDs is required in the request body.'}, status=status.HTTP_400_BAD_REQUEST)

        rows = RawActivityRow.objects.filter(id__in=row_ids, tenant=request.user.tenant, is_locked=False)
        approved_count = 0

        for row in rows:
            before_state = {'status': row.status}
            
            # Normalization
            kwh, co2e, ef_used, ef_src, flags = calculate_emissions(row)
            
            row.normalized_quantity_kwh = kwh
            row.normalized_quantity_kg_co2e = co2e
            row.emission_factor_used = ef_used
            row.emission_factor_source = ef_src
            row.flag_reasons = flags
            row.status = 'APPROVED'
            row.reviewed_by = request.user
            row.reviewed_at = timezone.now()
            row.save()

            AuditLog.objects.create(
                tenant=row.tenant,
                row=row,
                action='APPROVED',
                performed_by=request.user,
                before_state=before_state,
                after_state={
                    'status': row.status,
                    'normalized_quantity_kg_co2e': str(row.normalized_quantity_kg_co2e),
                    'emission_factor_used': str(row.emission_factor_used)
                }
            )
            approved_count += 1

        return Response({'message': f'Successfully approved {approved_count} rows.'})


# Review dashboard summary cards counts
class ReviewSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.user.tenant
        if not tenant:
            return Response({'error': 'No tenant associated with user'}, status=status.HTTP_400_BAD_REQUEST)

        # Get rows count by status
        status_counts = RawActivityRow.objects.filter(tenant=tenant).values('status').annotate(count=Count('id'))
        status_dict = {item['status']: item['count'] for item in status_counts}

        # Get rows count by scope
        scope_counts = RawActivityRow.objects.filter(tenant=tenant).values('scope').annotate(count=Count('id'))
        scope_dict = {item['scope']: item['count'] for item in scope_counts}

        # Get rows count by source_type
        source_counts = RawActivityRow.objects.filter(tenant=tenant).values('source_type').annotate(count=Count('id'))
        source_dict = {item['source_type']: item['count'] for item in source_counts}

        # Get count of total rows ingested this month
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total_this_month = RawActivityRow.objects.filter(tenant=tenant, created_at__gte=start_of_month).count()

        payload = {
            'total_this_month': total_this_month,
            'pending_review': status_dict.get('PENDING_REVIEW', 0),
            'flagged': status_dict.get('FLAGGED', 0),
            'approved': status_dict.get('APPROVED', 0),
            'rejected': status_dict.get('REJECTED', 0),
            'scopes': {
                'SCOPE_1': scope_dict.get('SCOPE_1', 0),
                'SCOPE_2': scope_dict.get('SCOPE_2', 0),
                'SCOPE_3': scope_dict.get('SCOPE_3', 0),
            },
            'sources': source_dict
        }
        return Response(payload)


# Audit CSV export and lock endpoint
class ExportAuditView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request):
        tenant = request.user.tenant
        
        # Select approved, unlocked rows
        approved_rows = RawActivityRow.objects.filter(tenant=tenant, status='APPROVED', is_locked=False)
        
        if not approved_rows.exists():
            # Return empty response or simple message in browser
            return Response({'error': 'No data ready for export', 'detail': 'There are no APPROVED and unlocked rows to export.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create HTTP Response with CSV headers
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="breathe_esg_audit_export_{timestamp}.csv"'

        writer = csv.writer(response)
        
        # Write CSV Header
        writer.writerow([
            'id', 'source_type', 'scope', 'activity_date', 'location', 'description', 
            'parsed_quantity', 'parsed_unit', 'normalized_quantity_kwh', 
            'normalized_quantity_kg_co2e', 'emission_factor_used', 'emission_factor_source', 
            'reviewed_by', 'reviewed_at', 'reviewer_note'
        ])

        # Write Rows and Lock them
        for row in approved_rows:
            writer.writerow([
                row.id,
                row.source_type,
                row.scope,
                row.activity_date,
                row.location,
                row.description,
                row.parsed_quantity,
                row.parsed_unit,
                row.normalized_quantity_kwh or '',
                row.normalized_quantity_kg_co2e,
                row.emission_factor_used,
                row.emission_factor_source,
                row.reviewed_by.username if row.reviewed_by else '',
                row.reviewed_at.isoformat() if row.reviewed_at else '',
                row.reviewer_note or ''
            ])

            # Lock the row
            before_state = {'is_locked': row.is_locked}
            row.is_locked = True
            row.save()

            # Audit Log
            AuditLog.objects.create(
                tenant=tenant,
                row=row,
                action='LOCKED',
                performed_by=request.user,
                before_state=before_state,
                after_state={'is_locked': True}
            )

        return response
