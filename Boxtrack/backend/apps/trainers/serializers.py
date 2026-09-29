from rest_framework import serializers

from apps.accounts.models import User
from apps.trainers.models import TrainerProfile


class TrainerProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    user_name = serializers.SerializerMethodField()
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = TrainerProfile
        fields = ['id', 'club', 'user', 'user_name', 'user_username', 'specialty', 'experience_years', 'professional_title', 'bio', 'created_at', 'updated_at']
        read_only_fields = ['club', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
