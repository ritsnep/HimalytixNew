from rest_framework import serializers

from .models import ConfigurationEntry, FeatureToggle


class ConfigurationEntrySerializer(serializers.ModelSerializer):
    organization_code = serializers.CharField(source="organization.code", read_only=True)

    class Meta:
        model = ConfigurationEntry
        fields = [
            "entry_id",
            "organization",
            "organization_code",
            "scope",
            "key",
            "value",
            "description",
            "is_sensitive",
            "updated_at",
        ]
        read_only_fields = fields


class FeatureToggleSerializer(serializers.ModelSerializer):
    organization_code = serializers.CharField(source="organization.code", read_only=True)

    class Meta:
        model = FeatureToggle
        fields = [
            "toggle_id",
            "organization",
            "organization_code",
            "module",
            "key",
            "is_enabled",
            "description",
            "metadata",
            "starts_on",
            "expires_on",
            "updated_at",
        ]
        read_only_fields = fields
