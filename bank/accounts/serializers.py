from rest_framework import serializers
from .models import *

class AccountTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountType
        fields = "__all__"
    
class AccountSerializer(serializers.ModelSerializer):
    account_type = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    class Meta:
        model = Account
        fields = "__all__"
    
    def get_account_type(self, obj):
        return obj.account_type.name

    def get_customer(self, obj):
        return {
            "id": obj.customer.id,
            "full_name": obj.customer.user.get_full_name(),
            "email": obj.customer.user.email
        }

class AccountStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountStatement
        fields = "__all__"
