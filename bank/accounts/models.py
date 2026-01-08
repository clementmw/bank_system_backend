from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from auth_service.models import *
from django.db.models import Q
from .utility import *
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver


class AccountType(BaseModel):
    """
    Defines different types of accounts available in the system
    """
    ACCOUNT_TYPE_CHOICES = (
        ('SAVINGS', 'Savings Account'),
        ('FIXED_DEPOSIT', 'Fixed Deposit'),
        ('BUSINESS', 'Business Account'),
    )

    
    name = models.CharField(max_length=50, unique=True, choices=ACCOUNT_TYPE_CHOICES)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField()
    minimum_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Annual interest rate in percentage",
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    monthly_maintenance_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    overdraft_allowed = models.BooleanField(default=False)
    overdraft_limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    requires_kyc_verification = models.BooleanField(default=True)
    
    # Tier-based eligibility
    eligible_tiers = models.JSONField(
        default=list,
        help_text="List of customer tiers eligible for this account type"
    )
    minimum_opening_balance = models.FloatField(default = 1000, validators=[MinValueValidator(0.0)])
    auto_activate = models.BooleanField(default=True) #auto activates on receiving deposst

    def __str__(self):
        return f"{self.get_name_display()} ({self.code})"

    class Meta:
        db_table = 'account_type'
        indexes = [
            models.Index(fields=['name', 'is_active']),
            models.Index(fields=['code']),
        ]
        permissions = [
            ("can_manage_account_types", "Can manage account types"),
            ("can_view_account_types", "Can view account types"),
        ]


class Account(BaseModel):
    """
    Core account model for all customer accounts
    """
    ACCOUNT_STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('FROZEN', 'Frozen'),
        ('CLOSED', 'Closed'),
        ('REJECTED', 'Rejected'),
        ('PENDING_APPROVAL', 'Pending Approval'),
    )
    
    CURRENCY_CHOICES = (
        ('KES', 'Kenyan Shilling'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    )
    ACCOUNT_CATEGORY_CHOICES = (
        ('CUSTOMER', 'Customer Account'),
        ('INTERNAL', 'Internal / System Account'),
    )
    
    category = models.CharField(max_length=20, choices=ACCOUNT_CATEGORY_CHOICES, default='CUSTOMER')
    account_number = models.CharField(max_length=20, unique=True, db_index=True)
    customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name='accounts', null=True,blank=True)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, related_name='accounts')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'),validators=[MinValueValidator(Decimal('-999999999999.99'))])  # Allow negative for overdraf )
    available_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Balance available for withdrawal (excludes holds)"
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='KES')
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='PENDING_APPROVAL')
    
    # Account metadata
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='closed_accounts'
    )
    closure_reason = models.TextField(blank=True, null=True)
    
    # Approval workflow
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_accounts'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Interest tracking
    last_interest_date = models.DateField(null=True, blank=True)
    accumulated_interest = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Flags
    is_primary = models.BooleanField(default=False)
    is_joint_account = models.BooleanField(default=False)
    allow_debit = models.BooleanField(default=True)
    allow_credit = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = generate_account_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_number} - {self.customer}"

    class Meta:
        db_table = 'account'
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['account_type', 'status']),
            models.Index(fields=['status', 'is_active']),
        ]
        permissions = [
            ("can_open_account", "Can open new accounts"),
            ("can_close_account", "Can close accounts"),
            ("can_freeze_account", "Can freeze accounts"),
            ("can_approve_account", "Can approve account opening"),
            ("can_view_all_accounts", "Can view all accounts"),
            ("can_modify_account_limits", "Can modify account limits"),
        ]



class AccountLimit(BaseModel):
    """
    Transaction limits per account
    """
    account = models.OneToOneField(
        Account, 
        on_delete=models.CASCADE, 
        related_name='limits'
    )
    
    # Daily limits
    daily_debit_limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    daily_credit_limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    daily_transaction_count_limit = models.IntegerField(
        default=50,
        validators=[MinValueValidator(1)]
    )
    
    # Per transaction limits
    single_transaction_debit_limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    single_transaction_credit_limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Monthly limits
    monthly_debit_limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    monthly_credit_limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Override tracking
    limit_override_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_limit_overrides'
    )
    limit_override_reason = models.TextField(blank=True, null=True)
    limit_override_expiry = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Limits for {self.account.account_number}"

    class Meta:
        db_table = 'account_limit'
        indexes = [
            models.Index(fields=['account']),
        ]
        permissions = [
            ("can_set_account_limits", "Can set account limits"),
            ("can_override_account_limits", "Can override account limits"),
        ]

@receiver(post_save, sender=AccountLimit)
def create_transaction_limits(sender, instance, created, **kwargs):
    """Auto-create TransactionLimit tracking records"""
    if created:
        from transactions.models import TransactionLimit, TransactionType
        
        # Create daily tracking for each transaction type
        for txn_type in [TransactionType.WITHDRAWAL, TransactionType.INTERNAL_TRANSFER]:
            TransactionLimit.objects.create(
                account=instance.account,
                account_limit=instance,
                transaction_type=txn_type,
                max_amount=instance.daily_debit_limit,
                max_count=instance.daily_transaction_count_limit,
                reset_at=timezone.now().replace(hour=0, minute=0) + timedelta(days=1)
            )
class AccountLimitOverrideRequest(BaseModel):
    """
    Requests for overriding account limits
    """
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='account_limit_override_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name='limit_override_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_daily_debit_limit = models.FloatField(max_length=15, validators=[MinValueValidator(0.0)])
    requested_daily_credit_limit = models.FloatField( max_length=15, validators=[MinValueValidator(0.0)])
    reason = models.TextField()
    status = models.CharField(max_length=20, default='PENDING')

    def __str__(self):
        return f"Limit override request for  {self.requested_by}"

    class Meta:
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['requested_by']),
        ]
        permissions = [
            ("can_approve_limit_overrides", "Can approve limit override requests"),
            ("can_view_limit_override_requests", "Can view limit override requests"),
        ]


class JointAccountHolder(BaseModel):
    """
    Additional holders for joint accounts
    """
    HOLDER_TYPE_CHOICES = (
        ('PRIMARY', 'Primary Holder'),
        ('SECONDARY', 'Secondary Holder'),
        ('GUARDIAN', 'Guardian'),
    )
    
    account = models.ForeignKey(
        Account, 
        on_delete=models.CASCADE, 
        related_name='joint_holders'
    )
    customer = models.ForeignKey(
        CustomerProfile, 
        on_delete=models.PROTECT, 
        related_name='joint_accounts'
    )
    holder_type = models.CharField(max_length=20, choices=HOLDER_TYPE_CHOICES)
    can_transact = models.BooleanField(default=True)
    can_view_statements = models.BooleanField(default=True)
    added_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    def __str__(self):
        return f"{self.customer.user.email} - {self.account.account_number}"

    class Meta:
        db_table = 'joint_account_holder'
        unique_together = ('account', 'customer')
        indexes = [
            models.Index(fields=['account', 'customer']),
        ]


class AccountStatement(BaseModel):
    """
    Periodic account statements
    """
    STATEMENT_TYPE_CHOICES = (
        ('MONTHLY', 'Monthly Statement'),
        ('QUARTERLY', 'Quarterly Statement'),
        ('ANNUAL', 'Annual Statement'),
        ('ON_DEMAND', 'On-Demand Statement'),
    )
    
    account = models.ForeignKey(
        Account, 
        on_delete=models.CASCADE, 
        related_name='statements'
    )
    statement_type = models.CharField(max_length=20, choices=STATEMENT_TYPE_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2)
    total_credits = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_debits = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    transaction_count = models.IntegerField(default=0)
    
    # File storage
    pdf_file = models.FileField(upload_to='statements/%Y/%m/', null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Delivery tracking
    sent_to_customer = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.account.account_number} - {self.statement_type} - {self.period_start} to {self.period_end}"

    class Meta:
        db_table = 'account_statement'
        indexes = [
            models.Index(fields=['account', 'period_start', 'period_end']),
            models.Index(fields=['statement_type', 'created_at']),
        ]
        permissions = [
            ("can_generate_statements", "Can generate account statements"),
            ("can_view_statements", "Can view account statements"),
        ]
        unique_together = ('account', 'statement_type', 'period_start', 'period_end')


class AccountHold(BaseModel):
    """
    Temporary holds on account funds (e.g., pending transactions, legal holds)
    """
    HOLD_TYPE_CHOICES = (
        ('TRANSACTION', 'Transaction Hold'),
        ('LEGAL', 'Legal Hold'),
        ('ADMINISTRATIVE', 'Administrative Hold'),
        ('FRAUD', 'Fraud Investigation Hold'),
    )
    
    account = models.ForeignKey(
        Account, 
        on_delete=models.CASCADE, 
        related_name='holds'
    )
    hold_type = models.CharField(max_length=20, choices=HOLD_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reason = models.TextField()
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    
    placed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='placed_holds'
    )
    placed_at = models.DateTimeField(auto_now_add=True)
    
    released_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='released_holds'
    )
    released_at = models.DateTimeField(null=True, blank=True)
    
    expiry_date = models.DateTimeField(null=True, blank=True)
    is_released = models.BooleanField(default=False)

    def __str__(self):
        return f"Hold on {self.account.account_number} - {self.amount} {self.account.currency}"

    class Meta:
        db_table = 'account_hold'
        indexes = [
            models.Index(fields=['account', 'is_released']),
            models.Index(fields=['reference_id']),
            models.Index(fields=['expiry_date']),
        ]
        permissions = [
            ("can_place_hold", "Can place holds on accounts"),
            ("can_release_hold", "Can release holds on accounts"),
        ]


class BeneficiaryAccount(BaseModel):
    """
    Saved beneficiary accounts for quick transfers
    """
    customer = models.ForeignKey(
        CustomerProfile, 
        on_delete=models.CASCADE, 
        related_name='beneficiaries'
    )
    beneficiary_name = models.CharField(max_length=100)
    beneficiary_account_number = models.CharField(max_length=20)
    beneficiary_bank = models.CharField(max_length=100)
    beneficiary_bank_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Optional details
    beneficiary_email = models.EmailField(blank=True, null=True)
    beneficiary_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Usage tracking
    nickname = models.CharField(max_length=50, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.beneficiary_name} - {self.beneficiary_account_number}"

    class Meta:
        db_table = 'beneficiary_account'
        indexes = [
            models.Index(fields=['customer', 'is_active']),
            models.Index(fields=['beneficiary_account_number']),
        ]
        unique_together = ('customer', 'beneficiary_account_number')
        permissions = [
            ("can_manage_beneficiaries", "Can manage beneficiary accounts"),
        ]