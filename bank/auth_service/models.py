from django.db import models
from .manager import CustomUserManager
from django.contrib.auth.models import AbstractUser, Permission
from django.utils import timezone
from datetime import timedelta
from .utility import *
from django.contrib.contenttypes.models import ContentType
import secrets



class Role(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'ADMIN'), #assumption it is the superadmin or system administrator
        ('CUSTOMER', 'CUSTOMER'),
        ('STAFF', 'STAFF'),

    )


    name = models.CharField(max_length=50, unique=True, choices=ROLE_CHOICES)
    permissions = models.ManyToManyField(Permission, blank=True,related_name="role_permissions")#specific roles for each role
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def add_permission_by_codename(self, codename, app_label):
        """Helper method to add permission by codename"""
        try:
            content_type = ContentType.objects.get(app_label=app_label)
            permission = Permission.objects.get(
                codename=codename,
                content_type=content_type
            )
            self.permissions.add(permission)
        except (ContentType.DoesNotExist, Permission.DoesNotExist):
            raise ValueError(f"Permission {codename} in app {app_label} not found")


class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.PROTECT,related_name="users")
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    email_verification_token = models.CharField(max_length=64, blank=True, null=True)
    email_verification_expiry = models.DateTimeField(blank=True, null=True)
    password = models.CharField(max_length=128)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

 
    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def set_otp(self):
        """
        Generate and set a one-time password.
        """
        self.otp = generate_otp()
        self.otp_expiry = timezone.now()
        self.save()

    def is_otp_valid(self):
        """Check if the OTP is still valid."""
        if self.otp_expiry:
            return timezone.now() < self.otp_expiry + timedelta(minutes=3)
        return False

    def generate_email_token(self):
        """Generate token for email verification"""
        token = secrets.token_hex(32)
        self.email_verification_token = token
        self.email_verification_expiry = timezone.now() + timedelta(hours=24)
        self.save()
        return token

    def verify_email(self, token):
        """Return True if token valid and email is verified"""
        if (
            self.email_verification_token == token and
            timezone.now() < self.email_verification_expiry
        ):
            self.is_active = True
            self.email_verification_token = None
            self.email_verification_expiry = None
            self.save()
            return True
        return False


    def __str__(self):
        return f"{self.first_name} - {self.role} - {self.last_name} - {self.email}"
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'role']),
            models.Index(fields=['role', 'is_active'])
        ]
        permissions = [
            ("view_account_balance", "Can view account balance"),
            ("transfer_funds", "Can transfer funds"),
            ("approve_transfer", "Can approve large transfers"),
            ("manage_users", "Can manage users"),
            ("view_transaction_history", "Can view transaction history"),
            ("manage_accounts", "Can create/close accounts"),
            ("override_limits", "Can override transaction limits"),
            ("view_audit_log", "Can view audit logs"),
            ("process_kyc", "Can process KYC verification"),
        ]
    

class EmployeeProfile(models.Model):
    DEPARTMENT_CHOICES = (
        ('FINANCE', 'Finance'),
        ('OPERATIONS', 'Operations'),
        ('IT', 'IT Support'),
        ('HR', 'Human Resources'),
        ('RISK', 'Risk & Compliance'),
        ('CUSTOMER_SERVICE', 'Customer Service'),
    )

    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES)
    job_title = models.CharField(max_length=100)
    date_of_hire = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, null=True, blank=True)
    is_active_employee = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee_id} - {self.user.email} ({self.job_title})"

    class Meta:
        indexes = [
            models.Index(fields=['employee_id', 'department']),
        ]
        permissions = [
            ("can_manage_employees", "Can manage employee records"),
            ("can_view_employee_details", "Can view employee details"),
        ]
        
        unique_together = ('user', 'employee_id')
class CustomerProfile(models.Model):
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='customer_profile')
    customer_id = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=20, unique=True)
    national_id = models.CharField(max_length=20, null=True,blank=True) #updated during kyc 
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    next_of_kin_name = models.CharField(max_length=100, null=True, blank=True)
    next_of_kin_contact = models.CharField(max_length=20, null=True, blank=True)
    occupation = models.CharField(max_length=100, null=True, blank=True)
    risk_rating = models.CharField(max_length=20, default='LOW', choices=[
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High')
    ])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Customer {self.customer_id} - {self.user.email}"

    class Meta:
        indexes = [
            models.Index(fields=['customer_id', 'phone_number']),
        ]
        permissions = [
            ("can_view_customer_accounts", "Can view customer accounts"),
            ("can_edit_customer_profile", "Can edit customer profile"),
        ]

        unique_together = ('user', 'customer_id')
 

class KycProfile(models.Model):
    DOCUMENT_TYPE_CHOICES = (
        ('ID', 'National ID'),
        ('PASSPORT', 'Passport'),
        ('DRIVERS_LICENSE', 'Drivers License'),
        ('VOTER_ID', 'Voter ID'),
        ('KRA_CERTIFICATE', 'Kra_certificate'),
        ('OTHER', 'Other') 
    )
    VERIFICATION_STATUS = {
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('UPLOADED','Uploaded')
    }
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc_profile")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    document_upload = models.FileField(upload_to='kyc_documents/',null=True,blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='PENDING')
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_kyc_profiles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.document_type}"
    
    # indexing for frequent querys
    class Meta:
        indexes = [
            models.Index(fields=['user', 'verification_status']),
        ]
        permissions = [
            ("can_process_kyc", "Can process KYC verification"),
            ("can_view_kyc", "Can view KYC details"),
            ("can_approve_kyc", "Can approve KYC verification"),
            ("can_reject_kyc", "Can reject KYC verification"),
            ("can_expire_kyc", "Can expire KYC verification"),
        ]
        



class SessionLogs(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="session_logs")
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    browser_agent = models.CharField(max_length=255, null=True, blank=True)  #browser used to access the system
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Session log for {self.user.email} at {self.login_time}" 
    
    # indexing for frequent querys
    class Meta:
        indexes = [
            models.Index(fields=['user', 'login_time']),
        ]

