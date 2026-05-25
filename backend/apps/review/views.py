from datetime import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.review.models import RawActivityRow
from apps.review.serializers import RawActivityRowSerializer
from apps.ingestion.parsers import calculate_emissions
from apps.export.models import AuditLog

# Base ViewSet to enforce tenant scoping
class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.tenant:
            return self.queryset.none()
        return self.queryset.filter(tenant=user.tenant)

class ReviewRowPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class RawActivityRowViewSet(TenantScopedViewSet):
    serializer_class = RawActivityRowSerializer
    pagination_class = ReviewRowPagination
    queryset = RawActivityRow.objects.all().order_by('-activity_date')

    def get_queryset(self):
        qs = super().get_queryset()
        
        status_param = self.request.query_params.get('status')
        source_param = self.request.query_params.get('source_type')
        scope_param = self.request.query_params.get('scope')
        flagged_only = self.request.query_params.get('flagged_only')
        
        date_start = self.request.query_params.get('date_start') or self.request.query_params.get('date_from')
        date_end = self.request.query_params.get('date_end') or self.request.query_params.get('date_to')

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

        qty_change = 'parsed_quantity' in request.data and Decimal(str(request.data['parsed_quantity'])) != row.parsed_quantity
        unit_change = 'parsed_unit' in request.data and request.data['parsed_unit'] != row.parsed_unit
        
        serializer = self.get_serializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        row.refresh_from_db()

        if qty_change or unit_change:
            row.edited_from_raw = True
            
            flags = []
            if row.parsed_quantity < 0:
                flags.append("Negative quantity detected")
            if row.source_type == 'UTILITY_ELECTRICITY' and row.parsed_quantity == 0:
                flags.append("Zero energy consumption reported")
            
            valid_units = ['liter', 'gallons', 'kg', 'pieces', 'MWh', 'kWh', 'miles', 'km', 'room-night']
            if row.parsed_unit not in valid_units:
                flags.append(f"Unrecognized unit: {row.parsed_unit}")

            row.flag_reasons = flags
            if flags:
                row.status = 'FLAGGED'
            elif row.status == 'FLAGGED':
                row.status = 'PENDING_REVIEW'
            
            row.save()

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

        kwh, co2e, ef_used, ef_src, flags = calculate_emissions(row)
        
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

        AuditLog.objects.create(
            tenant=row.tenant,
            row=row,
            action='REJECTED',
            performed_by=request.user,
            before_state=before_state,
            after_state={'status': row.status, 'reviewer_note': reviewer_note}
        )

        return Response(RawActivityRowSerializer(row).data)

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

class ReviewSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = request.user.tenant
        if not tenant:
            return Response({'error': 'No tenant associated with user'}, status=status.HTTP_400_BAD_REQUEST)

        status_counts = RawActivityRow.objects.filter(tenant=tenant).values('status').annotate(count=Count('id'))
        status_dict = {item['status']: item['count'] for item in status_counts}

        scope_counts = RawActivityRow.objects.filter(tenant=tenant).values('scope').annotate(count=Count('id'))
        scope_dict = {item['scope']: item['count'] for item in scope_counts}

        source_counts = RawActivityRow.objects.filter(tenant=tenant).values('source_type').annotate(count=Count('id'))
        source_dict = {item['source_type']: item['count'] for item in source_counts}

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
