from django.contrib import admin
from .models import *


admin.site.site_header = "EVERGREEN DASHBOARD "
admin.site.site_title = "EVERGREEN"
admin.site.index_title = "Welcome to Your your Dashboard"

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [field.name for field in User._meta.fields]


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = [field.name for field in EmployeeProfile._meta.fields]

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CustomerProfile._meta.fields]

@admin.register(SessionLogs)
class SessionLogsAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SessionLogs._meta.fields]
@admin.register(KycProfile)
class ApplicantKYCAdmin(admin.ModelAdmin):
	list_display = [field.name for field in KycProfile._meta.fields]

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Role._meta.fields]