from django.db import models
from auth_service.models import *
from accounts.models import *
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid





class TransactionType(models.TextChoices):
    """Transaction type choices"""
    INTERNAL_TRANSFER = 'INTERNAL_TRANSFER', 'Internal Transfer'
    DEPOSIT = 'DEPOSIT', 'Deposit'
    WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
    CARD_TRANSACTION = 'CARD_TRANSACTION', 'Card Transaction'
    MPESA_DEPOSIT = 'MPESA_DEPOSIT', 'M-Pesa Deposit'
    MPESA_WITHDRAWAL = 'MPESA_WITHDRAWAL', 'M-Pesa Withdrawal'
    REVERSAL = 'REVERSAL', 'Reversal'
    BATCH_TRANSFER = 'BATCH_TRANSFER', 'Batch Transfer'
    FEE = 'FEE', 'Fee'
    INTEREST = 'INTEREST', 'Interest'


class TransactionStatus(models.TextChoices):
    """Transaction status choices"""
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    REVERSED = 'REVERSED', 'Reversed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class LedgerEntryType(models.TextChoices):
    """Double-entry ledger entry types"""
    DEBIT = 'DEBIT', 'Debit'
    CREDIT = 'CREDIT', 'Credit'

class FeeRule(BaseModel):
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices, db_index=True)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['min_amount']
        unique_together = (
            'transaction_type',
            'min_amount',
            'max_amount'
        )

class Transaction(BaseModel):
    """Main transaction model - immutable after creation"""
    transaction_ref = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique transaction reference for external systems")
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices, db_index=True)
    trans_status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PENDING, db_index=True)
    source_account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT, related_name='outgoing_transactions', null=True, blank=True, db_index=True)
    destination_account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT, related_name='incoming_transactions', null=True, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField(max_length=3, default='KES')
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    source_balance_before = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    source_balance_after = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    destination_balance_before = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    destination_balance_after = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    external_ref = models.CharField(max_length=100, blank=True, db_index=True, help_text="External system reference (M-Pesa, card processor)")
    # card = models.ForeignKey('cards.Card', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    batch_transfer = models.ForeignKey('BatchTransfer', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    initiated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='initiated_transactions')
    reversed_transaction = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversal')
    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True, help_text="Unique key for duplicate request prevention")
    completed_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    version = models.IntegerField(default=0)

    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'trans_status']),
            models.Index(fields=['source_account', '-created_at']),
            models.Index(fields=['destination_account', '-created_at']),
            models.Index(fields=['transaction_type', 'trans_status']),
            models.Index(fields=['external_ref']),
            models.Index(fields=['created_at', 'transaction_type']),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='transaction_amount_positive'),
            models.CheckConstraint(condition=models.Q(fee__gte=0), name='transaction_fee_non_negative'),
        ]

    def __str__(self):
        return f"{self.transaction_ref} - {self.transaction_type} - {self.amount}"

    def save(self, *args, **kwargs):
        """Override save to implement optimistic locking"""
        if not self._state.adding:
            self.version = models.F('version') + 1
        super().save(*args, **kwargs)
        if not self._state.adding:
            self.refresh_from_db(fields=['version'])


class LedgerEntry(BaseModel):
    """Double-entry bookkeeping ledger"""
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name='ledger_entries')
    account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT, related_name='ledger_entries', db_index=True)
    entry_type = models.CharField(max_length=10, choices=LedgerEntryType.choices, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    balance_after = models.DecimalField(max_digits=15, decimal_places=2, help_text="Account balance after this entry")
    description = models.TextField()

    class Meta:
        db_table = 'ledger_entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', '-created_at']),
            models.Index(fields=['transaction', 'entry_type']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.entry_type} - {self.amount} - {self.account}"


class IdempotencyKey(BaseModel):
    """Idempotency key storage for duplicate request prevention"""
    key = models.CharField(max_length=255, db_index=True, unique=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='idempotency_keys')
    request_params = models.JSONField(help_text="Original request parameters for comparison")
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = 'idempotency_keys'

    def __str__(self):
        return f"{self.key} - {self.transaction.transaction_ref}"

    def is_expired(self):
        return timezone.now() > self.expires_at


class ReversalRequest(BaseModel):
    """Transaction reversal/chargeback requests"""

    class ReversalReason(models.TextChoices):
        FRAUD = 'FRAUD', 'Fraud'
        ERROR = 'ERROR', 'Error'
        CHARGEBACK = 'CHARGEBACK', 'Chargeback'
        CUSTOMER_REQUEST = 'CUSTOMER_REQUEST', 'Customer Request'
        SYSTEM_ERROR = 'SYSTEM_ERROR', 'System Error'
        DUPLICATE = 'DUPLICATE', 'Duplicate Transaction'

    class ReversalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        REJECTED = 'REJECTED', 'Rejected'
        FAILED = 'FAILED', 'Failed'

    original_transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name='reversal_requests')
    reversal_transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, null=True, blank=True, related_name='reversal_request_record')
    reason = models.CharField(max_length=30, choices=ReversalReason.choices)
    status = models.CharField(max_length=20, choices=ReversalStatus.choices, default=ReversalStatus.PENDING, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], help_text="Amount to reverse (can be partial)")
    notes = models.TextField(blank=True)
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reversal_requests')
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_reversals')
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reversal_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['original_transaction']),
        ]

    def __str__(self):
        return f"Reversal {self.id} - {self.original_transaction.transaction_ref}"


class BatchTransfer(BaseModel):
    """Batch transfer for bulk payments"""

    class BatchStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        VALIDATING = 'VALIDATING', 'Validating'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        PARTIAL = 'PARTIAL', 'Partially Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    batch_ref = models.CharField(max_length=50, unique=True, db_index=True)
    source_account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT, related_name='batch_transfers')
    status = models.CharField(max_length=20, choices=BatchStatus.choices, default=BatchStatus.PENDING, db_index=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    total_count = models.IntegerField(validators=[MinValueValidator(1)])
    successful_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_batch_transfers')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'batch_transfers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['source_account', '-created_at']),
        ]

    def __str__(self):
        return f"{self.batch_ref} - {self.total_count} transfers"


class BatchTransferItem(BaseModel):
    """Individual items within a batch transfer"""

    class ItemStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(BatchTransfer, on_delete=models.CASCADE, related_name='items')
    destination_account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT, related_name='batch_transfer_items')
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=ItemStatus.choices, default=ItemStatus.PENDING, db_index=True)
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='batch_item')
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'batch_transfer_items'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['batch', 'status']),
        ]

    def __str__(self):
        return f"Item {self.id} - {self.amount} to {self.destination_account}"


class TransactionLimit(BaseModel):
    """Transaction limits for accounts and users"""

    class LimitType(models.TextChoices):
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'
        MONTHLY = 'MONTHLY', 'Monthly'
        PER_TRANSACTION = 'PER_TRANSACTION', 'Per Transaction'

    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, related_name='transaction_limits', null=True, blank=True)
    account_limit = models.ForeignKey('accounts.AccountLimit', on_delete=models.PROTECT, related_name = 'usage_tracking')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transaction_limits', null=True, blank=True)
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    limit_type = models.CharField(max_length=20, choices=LimitType.choices, default=LimitType.DAILY)
    max_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    max_count = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)], help_text="Maximum number of transactions")
    current_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    current_count = models.IntegerField(default=0)
    reset_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'transaction_limits'
        unique_together = [
            ['account', 'transaction_type', 'limit_type'],
            ['user', 'transaction_type', 'limit_type'],
        ]
        indexes = [
            models.Index(fields=['account', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        scope = self.account or self.user
        return f"{scope} - {self.transaction_type} - {self.limit_type}"

    def check_limit(self, amount):
        """Check if adding this amount would exceed the limit"""
        return (self.current_amount + amount) <= self.max_amount

    def increment(self, amount):
        """Increment the current usage"""
        self.current_amount += amount
        self.current_count += 1
        self.save(update_fields=['current_amount', 'current_count', 'updated_at'])



class TransactionWebhook(BaseModel):
    """Webhook logs for external system notifications"""

    class WebhookStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
        RETRYING = 'RETRYING', 'Retrying'

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='webhooks')
    url = models.URLField()
    event_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=WebhookStatus.choices, default=WebhookStatus.PENDING)
    payload = models.JSONField()
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'transaction_webhooks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['transaction']),
        ]

    def __str__(self):
        return f"Webhook {self.id} - {self.transaction.transaction_ref}"
