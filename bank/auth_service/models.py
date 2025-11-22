from django.db import models
from .manager import CustomUserManager
from django.contrib.auth.models import AbstractUser, Permission
from django.utils import timezone
from datetime import timedelta
from .utility import *
from django.contrib.contenttypes.models import ContentType
import secrets



class BaseModel(models.Model):
    """Abstract base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Department(BaseModel):
    DEPARTMENT_CHOICES = (
        ('FINANCE', 'Finance'),
        ('OPERATIONS', 'Operations'),
        ('IT', 'IT Support'),
        ('HR', 'Human Resources'),
        ('RISK', 'Risk & Compliance'),
        ('CUSTOMER_SERVICE', 'Customer Service'),
    )
    name = models.CharField(max_length=50, unique=True, choices=DEPARTMENT_CHOICES)
    hod = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='hod_of_department')
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

class Role(BaseModel):
    """Enhanced role model with hierarchical support"""
    
    ROLE_CATEGORIES = (
        ('SYSTEM', 'System'),
        ('STAFF', 'Staff'),
        ('Customer', 'Customer'),
    )

    role_name = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=50, choices=ROLE_CATEGORIES)
    department_name = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    permissions = models.ManyToManyField(
        Permission,
        verbose_name='role permissions',
        blank=True,
        related_name='roles'
    )
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False)

    def __str__(self):
        return self.role_name 

    class Meta:
        db_table = 'auth_role'
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]
class User(AbstractUser,BaseModel):
    role = models.ForeignKey(Role, on_delete=models.PROTECT,related_name="users")
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    email_verification_token = models.CharField(max_length=64, blank=True, null=True)
    email_verification_expiry = models.DateTimeField(blank=True, null=True)
    password = models.CharField(max_length=128)  


 
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
            # User Management
            ("can_manage_users", "Can manage users"),
            ("can_view_user_profiles", "Can view user profiles"),
            
            # Finance
            ("view_account_balance", "Can view account balance"),
            ("transfer_funds", "Can transfer funds"),
            ("approve_transfer", "Can approve large transfers"),
            ("view_transaction_history", "Can view transaction history"),
            ("manage_accounts", "Can create/close accounts"),
            ("override_limits", "Can override transaction limits"),
            ("view_audit_log", "Can view audit logs"),
            ("process_kyc", "Can process KYC verification"),
            
            # System Administration
            ("can_manage_system_settings", "Can manage system settings"),
            ("can_view_system_logs", "Can view system logs"),
            
        ]


class EmployeeProfile(BaseModel):
    employment_type_choices = (
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
        ('INTERN', 'Intern'),
    )
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='employee_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    employment_type  = models.CharField(max_length=20, choices=employment_type_choices, default='FULL_TIME')
    job_title = models.CharField(max_length=100)
    date_of_hire = models.DateField(null=True, blank=True)
    date_of_termination = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, null=True, blank=True)
    is_active_employee = models.BooleanField(default=True)
    address = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_employees') #later used foraudit trail


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
class CustomerProfile(BaseModel):
    customer_tier_choices = (
        ('STANDARD','Standard'),
        ('PREMIUM','Premium'),
        ('BUSINESS','Business')
    )
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='customer_profile')
    customer_id = models.CharField(max_length=20, unique=True)
    customer_tier = models.CharField(max_length=20, choices=customer_tier_choices, default='STANDARD')
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
    preferred_communication_channel = models.CharField(max_length=20, default='EMAIL', choices=[
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('PHONE', 'Phone')
    ])
    marketing_preferences = models.BooleanField(default=False) #to use during newsletter




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
 
class KycProfile(BaseModel):
    VERIFICATION_STATUS = (
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('UNDER_REVIEW', 'Under Review'),
        ('INCOMPLETE', 'Incomplete')
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc_profile")
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='INCOMPLETE')
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_kyc_profiles")
    review_notes = models.TextField(blank=True, null=True)


    class Meta:
        indexes = [
            models.Index(fields=['user', 'verification_status']),
            models.Index(fields=['verification_status']),
        ]

    def __str__(self):
        return f"KYC Profile - {self.user.email} - {self.verification_status}"


class KycDocument(BaseModel):
  
    DOCUMENT_STATUS = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired')
    )

    kyc_profile = models.ForeignKey(KycProfile, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30)
    document_upload = models.FileField(upload_to='kyc_documents/')
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=DOCUMENT_STATUS, default='PENDING')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)


    class Meta:
        unique_together = ('kyc_profile', 'document_type')  # One document type per KYC profile
        indexes = [
            models.Index(fields=['kyc_profile', 'document_type']),
            models.Index(fields=['status']),
            models.Index(fields=['document_type']),
        ]

    def save(self, *args, **kwargs):
        if self.document_upload:
            self.file_name = self.document_upload.name
            self.file_size = self.document_upload.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kyc_profile.user.email} - {self.document_type} - {self.status}"



class SessionLogs(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="session_logs")
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    browser_agent = models.CharField(max_length=255, null=True, blank=True)  #browser used to access the system

    
    def __str__(self):
        return f"Session log for {self.user.email} at {self.login_time}" 
    
    # indexing for frequent querys
    class Meta:
        indexes = [
            models.Index(fields=['user', 'login_time']),
        ]


class AuditLogs(BaseModel):
    pass

