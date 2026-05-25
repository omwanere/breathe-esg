from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('EDITED', 'Edited'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('LOCKED', 'Locked'),
    ]

    tenant = models.ForeignKey('authentication.Tenant', on_delete=models.CASCADE, related_name='audit_logs')
    row = models.ForeignKey('review.RawActivityRow', on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'ingestion_auditlog'

    def __str__(self):
        return f"AuditLog {self.id} - {self.action} on Row {self.row.id}"
