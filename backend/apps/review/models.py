import uuid
from django.db import models
from django.conf import settings

class RawActivityRow(models.Model):
    SCOPE_CHOICES = [
        ('SCOPE_1', 'Scope 1'),
        ('SCOPE_2', 'Scope 2'),
        ('SCOPE_3', 'Scope 3'),
    ]

    STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Review'),
        ('FLAGGED', 'Flagged'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, related_name='activity_rows')
    ingestion_job = models.ForeignKey('ingestion.IngestionJob', on_delete=models.CASCADE, related_name='rows')
    source_type = models.CharField(max_length=50, choices=[
        ('SAP_FUEL', 'SAP Fuel'),
        ('SAP_PROCUREMENT', 'SAP Procurement'),
        ('UTILITY_ELECTRICITY', 'Utility Electricity'),
        ('TRAVEL_FLIGHT', 'Travel Flight'),
        ('TRAVEL_HOTEL', 'Travel Hotel'),
        ('TRAVEL_GROUND', 'Travel Ground'),
    ])
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    raw_data = models.JSONField(default=dict)
    
    parsed_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    parsed_unit = models.CharField(max_length=50)
    
    normalized_quantity_kwh = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    normalized_quantity_kg_co2e = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    
    activity_date = models.DateField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    
    emission_factor_used = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=255, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_REVIEW')
    flag_reasons = models.JSONField(default=list, blank=True)
    
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_rows')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_note = models.TextField(null=True, blank=True)
    
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_from_raw = models.BooleanField(default=False)

    class Meta:
        db_table = 'ingestion_rawactivityrow'

    def __str__(self):
        return f"ActivityRow {self.id} - {self.source_type} - {self.status}"
