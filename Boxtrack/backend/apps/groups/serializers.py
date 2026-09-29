from rest_framework import serializers

from apps.groups.models import Group


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'club', 'name', 'description', 'schedule', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['club', 'created_at', 'updated_at']
