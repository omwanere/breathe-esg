from rest_framework import serializers
from esg_platform.models import Tenant, User, DataSource, IngestionJob, RawActivityRow, AuditLog

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'tenant']

class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ['id', 'source_type', 'ingestion_mode', 'created_at', 'last_ingested_at', 'config']

class IngestionJobSerializer(serializers.ModelSerializer):
    data_source_display = serializers.CharField(source='data_source.get_source_type_display', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            'id', 'data_source', 'data_source_display', 'source_type', 'status', 
            'started_at', 'completed_at', 'row_count', 'error_count', 'error_log', 
            'triggered_by_username'
        ]

class RawActivityRowSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = RawActivityRow
        fields = [
            'id', 'source_type', 'source_type_display', 'scope', 'scope_display', 
            'raw_data', 'parsed_quantity', 'parsed_unit', 'normalized_quantity_kwh', 
            'normalized_quantity_kg_co2e', 'activity_date', 'period_start', 'period_end', 
            'location', 'description', 'emission_factor_used', 'emission_factor_source', 
            'status', 'status_display', 'flag_reasons', 'reviewed_by_username', 
            'reviewed_at', 'reviewer_note', 'is_locked', 'created_at', 'updated_at', 
            'edited_from_raw'
        ]
        read_only_fields = ['id', 'source_type', 'scope', 'raw_data', 'is_locked', 'created_at', 'updated_at', 'edited_from_raw']
