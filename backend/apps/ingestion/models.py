from django.db import models
from django.conf import settings

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

    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, related_name='data_sources')
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
