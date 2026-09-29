from rest_framework import serializers

from apps.clubs.models import Club


class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['id', 'name', 'description', 'address', 'phone', 'email', 'website', 'is_active']
