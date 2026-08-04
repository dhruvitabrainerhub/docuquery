from rest_framework import serializers
from .models import Documents


class DocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Documents
        fields = ['id', 'title', 'file', 'user', 'upload_at', 'processed', 'status']
        read_only_fields = ['user', 'upload_at', 'processed', 'status']

    def validate_file(self, value):
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError('Only PDF files are allowed.')
        return value

