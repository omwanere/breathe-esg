import csv
from datetime import datetime
from django.db import transaction
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.review.models import RawActivityRow
from apps.export.models import AuditLog

class ExportAuditView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request):
        tenant = request.user.tenant
        
        approved_rows = RawActivityRow.objects.filter(tenant=tenant, status='APPROVED', is_locked=False)
        
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="breathe_esg_audit_export_{timestamp}.csv"'

        writer = csv.writer(response)
        
        writer.writerow([
            'id', 'source_type', 'scope', 'activity_date', 'location', 'description', 
            'parsed_quantity', 'parsed_unit', 'normalized_quantity_kwh', 
            'normalized_quantity_kg_co2e', 'emission_factor_used', 'emission_factor_source', 
            'reviewed_by', 'reviewed_at', 'reviewer_note'
        ])

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

            before_state = {'is_locked': row.is_locked}
            row.is_locked = True
            row.save()

            AuditLog.objects.create(
                tenant=tenant,
                row=row,
                action='LOCKED',
                performed_by=request.user,
                before_state=before_state,
                after_state={'is_locked': True}
            )

        return response
