from rest_framework import serializers
from .models import Documents

class DocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documents
        fields = ['id','title','file','upload_at','processed']
        read_only_fields = ('id','upload_at','processed')

    def validate_file(self,value):
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError('Only PDF files are supported.')
            return value