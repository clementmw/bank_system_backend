from django.contrib import admin
from .models import *
from .utility import generate_account_number


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display =[field.name for field in AccountType._meta.fields]
    search_fields = ("code","name")

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display =[field.name for field in Account._meta.fields]
    search_fields = ("account_number","customer")

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = generate_account_number()
            super().save(*args, **kwargs)
