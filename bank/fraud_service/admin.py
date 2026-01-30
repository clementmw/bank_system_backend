from django.contrib import admin
from .models import * 



@admin.register(FraudDetection)
class FraudDetectionAdmin(admin.ModelAdmin):
    list_display = [field.name for field in FraudDetection._meta.fields]
    search_fields = ("account_nummber", "transaction_type")

    def has_add_permission(self, request): #prevents manual data adding
        return False

