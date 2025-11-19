from django.contrib import admin
from .models import *
from .utility import *
from guardian.admin import GuardedModelAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin




admin.site.site_header = "EVERGREEN DASHBOARD "
admin.site.site_title = "EVERGREEN"
admin.site.index_title = "Welcome to Your your Dashboard"

class UserAdmin(GuardedModelAdmin):

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "role"),
        }),
    )
    
    list_display = [field.name for field in User._meta.fields]
    search_fields = ("email",)
    ordering = ("email",)

    def save_model(self, request, obj, form, change):
        # If password was manually entered, hash it
        raw_password = form.cleaned_data.get("password")
        if raw_password and not raw_password.startswith("pbkdf2_"):
            obj.set_password(raw_password)
        super().save_model(request, obj, form, change)

admin.site.register(User, UserAdmin)

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = [field.name for field in EmployeeProfile._meta.fields]

    # generate employee id
    def save_model(self, request, obj, form, change):
        if not obj.employee_id:
            obj.employee_id = generate_employee_id()
        super().save_model(request, obj, form, change)

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
    list_display = ("role_name", "department_name", "is_active", "is_system_role")
    search_fields = ("role_name","department_name")
    list_filter = ("category", "is_system_role", "is_active")
    filter_horizontal = ("permissions",)  

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Department._meta.fields]

