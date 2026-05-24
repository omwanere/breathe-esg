import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    
    class Meta:
        db_table = 'auth_user'

    def __str__(self):
        return f"{self.username} ({self.tenant.name if self.tenant else 'No Tenant'})"

class DataSource(models.Model):
    SOURCE_TYPES = [
        ('SAP_FUEL', 'SAP Fuel'),
        ('SAP_PROCUREMENT', 'SAP Procurement'),
        ('UTILITY_ELECTRICITY', 'Utility Electricity'),
        ('TRAVEL_FLIGHT', 'Travel Flight'),
        ('TRAVEL_HOTEL', 'Travel Hotel'),
        ('TRAVEL_GROUND', 'Travel Ground'),
    ]
    
    INGESTION_MODES = [
        ('FILE_UPLOAD', 'File Upload'),
        ('API_PULL', 'API Pull'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    ingestion_mode = models.CharField(max_length=20, choices=INGESTION_MODES, default='FILE_UPLOAD')
    created_at = models.DateTimeField(auto_now_add=True)
    last_ingested_at = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.tenant.name} - {self.get_source_type_display()}"

class IngestionJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='ingestion_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    raw_file = models.FileField(upload_to='ingestion_files/', null=True, blank=True)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_log = models.JSONField(default=list, blank=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Job {self.id} ({self.data_source.source_type}) - {self.status}"

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
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='activity_rows')
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='rows')
    source_type = models.CharField(max_length=50, choices=DataSource.SOURCE_TYPES)
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

    def __str__(self):
        return f"ActivityRow {self.id} - {self.source_type} - {self.status}"

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('EDITED', 'Edited'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('LOCKED', 'Locked'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs')
    row = models.ForeignKey(RawActivityRow, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"AuditLog {self.id} - {self.action} on Row {self.row.id}"

class UnitConversion(models.Model):
    from_unit = models.CharField(max_length=50)
    to_unit = models.CharField(max_length=50)
    factor = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=255, blank=True, default='')
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('from_unit', 'to_unit')

    def __str__(self):
        return f"{self.from_unit} -> {self.to_unit} ({self.factor})"

class EmissionFactor(models.Model):
    activity_type = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    unit = models.CharField(max_length=50)
    factor_kg_co2e_per_unit = models.DecimalField(max_digits=18, decimal_places=6)
    source = models.CharField(max_length=255)
    valid_year = models.IntegerField()

    def __str__(self):
        return f"{self.activity_type} ({self.region}) - {self.factor_kg_co2e_per_unit} kg CO2e / {self.unit} ({self.source} {self.valid_year})"
