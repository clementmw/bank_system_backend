from django.db import models
from auth_service.models import BaseModel
from transactions.models import  Transaction



class FraudDetection(BaseModel):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name = 'fraud_check', null=True, blank=True)
    account_number = models.CharField(max_length = 50)
    amount = models.DecimalField(max_digits = 50, decimal_places = 2)
    transaction_type = models.CharField(max_length = 50)
    risk_score = models.IntegerField()
    decision = models.CharField(max_length = 100)
    reason  = models.TextField()
    flags = models.JSONField(default=list)
    checked_at = models.DateTimeField(auto_now_add=True)
    processing_time_ms = models.IntegerField(null=True, blank=True)


    class meta:
        db_table = 'fraud_detection_logs'
        ordering = ['-checked_at']


    def __str__(self):
        return f"{self.transaction} - {self.decision}  - {self.account_number}"



