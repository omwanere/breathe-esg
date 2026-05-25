from rest_framework import serializers
from apps.ingestion.models import DataSource, IngestionJob

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
