from django.contrib import admin
from .models import *


@admin.register(FeeRule)
class FeeRuleAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'min_amount', 'max_amount', 'fee_amount')
    list_filter = ('transaction_type',)
    search_fields = ('transaction_type',)