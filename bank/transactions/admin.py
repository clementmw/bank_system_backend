from django.contrib import admin
from .models import *


@admin.register(FeeRule)
class FeeRuleAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'min_amount', 'max_amount', 'fee_amount')
    list_filter = ('transaction_type',)
    search_fields = ('transaction_type',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'amount', 'fee', 'created_at')
    list_filter = ('transaction_type',)
    search_fields = ('transaction_type',)

@admin.register(TransactionLimit)
class TransactionLimitAdmin(admin.ModelAdmin):
    list_display =[field.name for field in TransactionLimit._meta.fields]

    