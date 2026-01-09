from rest_framework import serializers
from .models import *


class TransactionSerializer(serializers.ModelSerializer):
    """Optimized transaction serializer for history"""

    
    class Meta:
        model = Transaction
        fields = ['transaction_ref','transaction_type','trans_status','amount', 'currency','source_balance_before', 'source_balance_after','fee']
    
