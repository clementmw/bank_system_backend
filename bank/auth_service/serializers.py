# handle serializer for auth 
from .models import *
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email','password','role']

        extra_kwargs = {
            'password': {"write_only":True},
            'role':{"required": True}
        }
    def create(self,validated_data):
        password = validated_data.pop('password',None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        
        instance.save()
        return instance
    

class EmployeeProfileSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    class Meta:
        model = EmployeeProfile
        fields = ['id','user','employee_id','department','employment_type','job_title','date_of_hire']
    
    def get_user(self, obj):
        return {
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name,
            "email": obj.user.email,
        }
    def get_department(self, obj):
        return {
            "name": obj.department.name if obj.department else None
        }

class EmployeeCompensationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeCompensation
        fields = '__all__'


class EmployeeData(serializers.ModelSerializer):
    compensation = EmployeeCompensationSerializer(read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = '__all__'


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = '__all__'


class KycDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KycDocument
        fields = '__all__'
        

class KycProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    documents = KycDocumentSerializer(many=True, read_only=True)
    verified_by_email = serializers.EmailField(source='verified_by.email', read_only=True)
    
    class Meta:
        model = KycProfile
        fields = [
            'id', 'user', 'user_email', 'user_full_name', 
            'verification_status', 'verified_at', 'verified_by', 
            'verified_by_email', 'review_notes', 'documents',
            'created_at', 'updated_at'
        ]

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'

