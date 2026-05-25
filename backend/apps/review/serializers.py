from rest_framework import serializers
from apps.review.models import RawActivityRow

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
