from rest_framework import serializers
from .models import Documents

class DocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documents
        fields = ['id','title','file']

