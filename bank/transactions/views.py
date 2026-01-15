from django.shortcuts import render
from .models import *
from .serializers import *
from .services.utility import *
# from .tasks import *
from .metrics import *
from .permissions import *
from django.http import HttpResponse
from auth_service.models import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed,APIException
from rest_framework.permissions import IsAuthenticated,BasePermission
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Sum, F
from decimal import Decimal
from .metrics import *
from .documentation import v1
from .tasks import *
from .services import utility,validations
from django.db import transaction as db_transaction
import logging
import requests

logger = logging.getLogger(__name__)



# transaction types
# 1. account to account
# 2. business to customer - withdraw ,reversal, 
# 3. customer to business - deposit
# 4. account to external account - api connection

class LimitExceeded(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Transaction limit exceeded"
    default_code = "limit_exceeded"



def validate_transaction_limits(account, amount, transaction_type):
    """
    Step 1: Check AccountLimit (static boundaries)
    Step 2: Check TransactionLimit (current usage)
    """
    logger.debug(f"Validating transaction limits for account {account.id}, amount: {amount}, type: {transaction_type}")
    
    # Step 1: Get static limits
    account_limit = account.limits  # OneToOne relationship
    
    # Validate against per-transaction limit
    if amount > account_limit.single_transaction_debit_limit:
        logger.warning(f"Amount {amount} exceeds per-transaction limit {account_limit.single_transaction_debit_limit}")
        raise Exception(
            f"Amount {amount} exceeds per-transaction limit "
            f"{account_limit.single_transaction_debit_limit}"
        )
    
    # Step 2: Get current usage
    today_limit = TransactionLimit.objects.get(
        account=account,
        transaction_type=transaction_type,
        limit_type='DAILY',
        is_active=True
    )
    
    logger.debug(f"Current daily limit usage: {today_limit.current_amount}/{today_limit.max_amount}")
    
    # Check if limit period expired
    if timezone.now() > today_limit.reset_at:
        logger.info(f"Resetting daily limit for account {account.id}")
        today_limit.current_amount = Decimal('0.00')
        today_limit.current_count = 0
        today_limit.reset_at = timezone.now().replace(hour=0, minute=0) + timedelta(days=1)
        today_limit.save()
    
    # Validate against daily limit
    if (today_limit.current_amount + amount) > today_limit.max_amount:
        logger.warning(f"Daily limit exceeded for account {account.id}")
        raise LimitExceeded(
            f"Daily limit exceeded. Used: {today_limit.current_amount}, "
            f"Requesting: {amount}, Limit: {today_limit.max_amount}"
        )
    
    # Validate transaction count
    if (today_limit.current_count + 1) > today_limit.max_count:
        logger.warning(f"Daily transaction count exceeded for account {account.id}")
        raise LimitExceeded(
            f"Daily transaction count exceeded. "
            f"Count: {today_limit.current_count}/{today_limit.max_count}"
        )
    
    logger.debug(f"Transaction limits validation passed for account {account.id}")
    return True

def validate_limits(account, amount, transaction_type):
    """
    Validates transaction against AccountLimit and TransactionLimit
    """
    logger.debug(f"validate_limits called for account {account.id}, amount: {amount}, type: {transaction_type}")
    
    # Step 1: Check static AccountLimit
    account_limit = account.limits
    logger.debug(f"Account limit: {account_limit}")
    
    if amount > account_limit.single_transaction_debit_limit:
        logger.warning(f"Amount exceeds single transaction limit for account {account.id}")
        raise Exception(
            f"Exceeds single transaction limit of "
            f"{account_limit.single_transaction_debit_limit}"
        )
    # Step 2: Check dynamic TransactionLimit
    daily_limit = TransactionLimit.objects.filter(
        account=account,
        transaction_type=transaction_type,
        limit_type='DAILY',
        is_active=True
    ).first()

    if not daily_limit:
        logger.error(f"Transaction limit not configured for account {account.id}")
        raise ValidationError("Transaction limit not configured for this account")

    logger.debug(f"Daily limit details: {daily_limit}")
    
    # Auto-reset if period expired
    if timezone.now() > daily_limit.reset_at:
        logger.info(f"Auto-resetting expired daily limit for account {account.id}")
        daily_limit.current_amount = Decimal('0.00')
        daily_limit.current_count = 0
        daily_limit.reset_at = timezone.now().replace(
            hour=0, minute=0, second=0
        ) + timedelta(days=1)
        daily_limit.save()
    
    logger.debug(f"Passed account limit check for account {account.id}")
    
    # Validate daily amount
    projected_usage = daily_limit.current_amount + amount
    if projected_usage > daily_limit.max_amount:
        logger.warning(f"Daily amount limit would be exceeded for account {account.id}")
        raise Exception(
            f"Daily limit exceeded. "
            f"Used: {daily_limit.current_amount}, "
            f"Requesting: {amount}, "
            f"Limit: {daily_limit.max_amount}, "
            f"Remaining: {daily_limit.max_amount - daily_limit.current_amount}"
        )
    
    # Validate transaction count
    if (daily_limit.current_count + 1) > daily_limit.max_count:
        logger.warning(f"Daily transaction count limit would be exceeded for account {account.id}")
        raise Exception(
            f"Daily transaction count limit exceeded: "
            f"{daily_limit.current_count}/{daily_limit.max_count}"
        )
    
    logger.debug(f"All limit validations passed for account {account.id}")
    return True


def authorize_user(user, source_account):
    """
    Verifies user has permission to transact on account
    """
    logger.debug(f"Authorizing user {user.id} for account {source_account.id}")
    
    # Check ownership
    is_owner = source_account.customer.user == user
    
    # Check joint account holder
    is_joint_holder = source_account.joint_holders.filter(
        customer__user=user,
        can_transact=True
    ).exists()
    
    if not (is_owner or is_joint_holder):
        logger.warning(f"User {user.id} not authorized for account {source_account.id}")
        raise PermissionDenied("User not authorized for this account")
    
    logger.debug(f"User {user.id} authorized for account {source_account.id}")
    return True

def validate_business_rules(amount, transaction_type, source_account, destination_account):
    """
    Enforces business-specific rules
    """
    logger.debug(f"Validating business rules for transaction: amount={amount}, type={transaction_type}")
    
    # Minimum transaction amount
    if amount < Decimal('1.00'):
        logger.warning(f"Transaction amount {amount} below minimum")
        raise ValidationError("Minimum transaction amount is 1.00")
    
    # Maximum transaction amount (fraud prevention)
    if amount > Decimal('10000000.00'):  # 10M
        logger.warning(f"Transaction amount {amount} exceeds maximum")
        raise ValidationError("Amount exceeds maximum allowed")
    
    # Check account type restrictions
    if source_account.account_type.name == 'FIXED_DEPOSIT':
        if transaction_type == TransactionType.WITHDRAWAL:
            logger.warning(f"Withdrawal attempt on fixed deposit account {source_account.id}")
            raise ValidationError(
                "Withdrawals not allowed on fixed deposit accounts"
            )
    
    # Currency validation
    if source_account.currency != destination_account.currency:
        logger.warning(f"Currency mismatch: {source_account.currency} vs {destination_account.currency}")
        # Forex conversion needed - not implemented yet
        raise ValidationError("Cross-currency transfers not supported")
    
    logger.debug(f"Business rules validation passed")
    return True

def validate_accounts(source_id, destination_id):
    """
    Validates accounts are active and operational
    """
    logger.debug(f"Validating accounts: source={source_id}, destination={destination_id}")
    
    # Get accounts with related data in single query
    source = Account.objects.select_related(
        'customer__user',
        'account_type',
        'limits'
    ).get(account_number=source_id)
    
    destination = Account.objects.select_related(
        'customer__user',
        'account_type'
    ).get(account_number=destination_id)
    
    # Validation checks
    checks = [
        (source.status == 'ACTIVE', "Source account not active"),
        (destination.status == 'ACTIVE', "Destination account not active"),
        (source.status != 'FROZEN', "Source account is frozen"),
        (destination.status != 'FROZEN', "Destination account is frozen"),
        (source.status != 'CLOSED', "Source account is closed"),
        (destination.status != 'CLOSED', "Destination account is closed"),
        (source.allow_debit, "Debit not allowed on source account"),
        (destination.allow_credit, "Credit not allowed on destination account"),
        (source.id != destination.id, "Cannot transfer to same account"),
    ]
    
    for condition, error_msg in checks:
        if not condition:
            logger.warning(f"Account validation failed: {error_msg}")
            raise ValidationError(error_msg)
    
    logger.debug(f"Account validation passed")
    return source, destination

def calculate_transaction_fee(amount, transaction_type):
    logger.debug(f"Calculating fee for amount={amount}, type={transaction_type}")
    
    rule = FeeRule.objects.filter(
        transaction_type=transaction_type,
        min_amount__lte=amount,
        max_amount__gte=amount,
        is_active=True
    ).first()

    if not rule:
        logger.debug(f"No fee rule found, returning 0")
        return Decimal('0.00')

    logger.debug(f"Fee calculated: {rule.fee_amount}")
    return rule.fee_amount


def check_available_balance(account, amount, fee):
    """
    Calculates available balance considering holds
    """
    logger.debug(f"Checking available balance for account {account.id}: amount={amount}, fee={fee}")
    
    # Get active holds
    total_holds = AccountHold.objects.filter(
        account=account,
        is_released=False,
        expiry_date__gt=timezone.now()
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Calculate available balance
    available = account.available_balance
    
    # Total amount needed
    total_needed = amount + fee
    
    logger.debug(f"Balance check: available={available}, total_needed={total_needed}, holds={total_holds}")
    
    if account.available_balance < total_needed:
        logger.warning(f"Insufficient funds for account {account.id}")
        raise Exception(
            f"Insufficient funds. "
            f"Balance: {account.balance}, "
            f"Holds: {total_holds}, "
            f"Available: {account.available_balance}, "
            f"Required: {total_needed}"
        )
    
    logger.debug(f"Available balance check passed")
    return available

def create_ledger_entries(transaction, source_account, dest_account):
    """
    Creates double-entry ledger entries
    
    For every transaction:
    - DEBIT from source account
    - CREDIT to destination account
    - If fee > 0: DEBIT fee from source, CREDIT to system account
    """
    logger.debug(f"Creating ledger entries for transaction {transaction.id}")
    
    entries = []
    
    # Entry 1: DEBIT source account
    entries.append(LedgerEntry(
        transaction=transaction,
        account=source_account,
        entry_type=LedgerEntryType.DEBIT,
        amount=transaction.amount,
        balance_after=transaction.source_balance_after,
        description=f"Transfer to {dest_account.account_number}"
    ))
    
    # Entry 2: CREDIT destination account
    entries.append(LedgerEntry(
        transaction=transaction,
        account=dest_account,
        entry_type=LedgerEntryType.CREDIT,
        amount=transaction.amount,
        balance_after=transaction.destination_balance_after,
        description=f"Transfer from {source_account.account_number}"
    ))
    
    # Entry 3 & 4: Fee entries (if applicable)
    if transaction.fee > Decimal('0.00'):
        logger.debug(f"Creating fee ledger entries: {transaction.fee}")
        # Get system fee account
        system_account = Account.objects.get(
            account_number='SYSTEM_FEE_ACCOUNT',
            category='INTERNAL'
        )
        
        # DEBIT fee from source
        entries.append(LedgerEntry(
            transaction=transaction,
            account=source_account,
            entry_type=LedgerEntryType.DEBIT,
            amount=transaction.fee,
            balance_after=transaction.source_balance_after,
            description=f"Transaction fee"
        ))
        
        # CREDIT fee to system
        entries.append(LedgerEntry(
            transaction=transaction,
            account=system_account,
            entry_type=LedgerEntryType.CREDIT,
            amount=transaction.fee,
            balance_after=system_account.balance,
            description=f"Fee from {source_account.account_number}"
        ))
    
    # Bulk create all entries
    LedgerEntry.objects.bulk_create(entries)
    logger.debug(f"Created {len(entries)} ledger entries")
    
    return entries

def update_transaction_limits(transaction):
    """
    Increments current usage in TransactionLimit
    """
    logger.debug(f"Updating transaction limits for transaction {transaction.id}")
    
    limit = TransactionLimit.objects.select_for_update().get(
        account=transaction.source_account,
        transaction_type=transaction.transaction_type,
        limit_type='DAILY'
    )
    
    logger.debug(f"Previous limit usage: {limit.current_amount}, count: {limit.current_count}")
    
    # Atomic increment
    limit.current_amount = F('current_amount') + transaction.amount
    limit.current_count = F('current_count') + 1
    limit.save(update_fields=['current_amount', 'current_count', 'updated_at'])
    
    logger.debug(f"Transaction limits updated")



@transaction.atomic
def execute_transaction(transaction_obj):
    """
    Executes the financial transaction with proper locking
    """
    logger.info(f"Starting transaction execution for transaction {transaction_obj.id}")
    
    # # Set isolation level
    # db_transaction.set_isolation_level('read committed')
    
    # Step 1: Lock accounts (order by ID to prevent deadlock)
    logger.debug(f"Acquiring locks on accounts")
        
    source_account = Account.objects.select_for_update().get(
        id=transaction_obj.source_account_id
    )

    destination_account = Account.objects.select_for_update().get(
        id=transaction_obj.destination_account_id
    )

    logger.debug(f"Locks acquired on accounts {source_account.id} and {destination_account.id}")
    
    # Step 2: Re-validate after acquiring lock
    logger.debug(f"Re-validating balance after lock")
    check_available_balance(
        source_account, 
        transaction_obj.amount, 
        transaction_obj.fee
    )
    
    # Step 3: Update transaction to PROCESSING
    logger.debug(f"Updating transaction {transaction_obj.id} to PROCESSING")
    transaction_obj.trans_status = TransactionStatus.PROCESSING
    transaction_obj.save(update_fields=['trans_status', 'updated_at'])
    
    # Step 4: Record balance snapshots
    logger.debug(f"Recording balance snapshots - before: source={source_account.balance}, dest={destination_account.balance}")
    transaction_obj.source_balance_before = source_account.balance
    transaction_obj.destination_balance_before = destination_account.balance
    
    # Step 5: Update source account (ATOMIC)
    logger.debug(f"Deducting from source account")
    total_deduction = transaction_obj.amount + transaction_obj.fee
    source_account.balance = F('balance') - total_deduction
    source_account.available_balance = F('available_balance') - total_deduction
    source_account.save(update_fields=['balance', 'available_balance', 'updated_at'])
    
    # Step 6: Update destination account (ATOMIC)
    logger.debug(f"Crediting to destination account")
    destination_account.balance = F('balance') + transaction_obj.amount
    destination_account.available_balance = F('available_balance') + transaction_obj.amount
    destination_account.save(update_fields=['balance', 'available_balance', 'updated_at'])

    # update the fee account if it applies 
    if transaction_obj.fee > Decimal('0.00'):
        fee_account = Account.objects.get(account_number='SYSTEM_FEE_ACCOUNT')
        fee_account.balance = F('balance') + transaction_obj.fee
        fee_account.available_balance = F('available_balance') + transaction_obj.fee
        fee_account.save(update_fields=['balance', 'available_balance', 'updated_at'])
    
    # Step 7: Refresh to get actual values
    logger.debug(f"Refreshing account data from DB")
    source_account.refresh_from_db()
    destination_account.refresh_from_db()
    
    # Step 8: Record balance snapshots (after)
    logger.debug(f"Recording balance snapshots - after: source={source_account.balance}, dest={destination_account.balance}")
    transaction_obj.source_balance_after = source_account.balance
    transaction_obj.destination_balance_after = destination_account.balance
    
    # Step 9: Create ledger entries
    logger.debug(f"Creating ledger entries")
    create_ledger_entries(
        transaction_obj,
        source_account,
        destination_account
    )
    
    # Step 10: Update transaction limits
    logger.debug(f"Updating transaction limits")
    update_transaction_limits(transaction_obj)
    
    # Step 11: Mark transaction as completed
    logger.info(f"Marking transaction {transaction_obj.id} as COMPLETED")
    transaction_obj.trans_status = TransactionStatus.COMPLETED
    transaction_obj.completed_at = timezone.now()
    transaction_obj.version = F('version') + 1
    transaction_obj.save(update_fields=[
        'trans_status', 
        'completed_at', 
        'version',
        'source_balance_before',
        'source_balance_after',
        'destination_balance_before',
        'destination_balance_after',
        'updated_at'
    ])
    
    # Step 12: Store idempotency key
    logger.debug(f"Storing idempotency key")
    IdempotencyKey.objects.create(
        key=transaction_obj.idempotency_key,
        transaction=transaction_obj,
        request_params=transaction_obj.metadata.get('request_params', {}),
        expires_at=timezone.now() + timedelta(hours=24)
    )
    
    logger.info(f"Transaction {transaction_obj.id} completed successfully")
    return transaction_obj

class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return request.user.role and request.user.role.role_name == "Customer"

class HandleInternalTransaction(APIView):
    """
    internal transfer account to account 
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def post(self,request):
        logger.info(f"Internal transaction request from user {request.user.id}")
        
        user = request.user

        data = request.data

        account_number = data.get('account_number')
        destination_account_number = data.get('destination_account_number')
        amount = data.get('amount')
        transaction_type = data.get('transaction_type').upper()
        idempotency_Key = request.headers.get('Idempotency-Key')  #to be passed by frontend

        logger.debug(f"Transaction params: source={account_number}, dest={destination_account_number}, amount={amount}, type={transaction_type}")

        if not idempotency_Key:
            logger.warning(f"Idempotency key missing in request from user {user.id}")
            return Response({"error":"idempotency key missing in request header"}, status = status.HTTP_404_NOT_FOUND)
        

        # validate account
        logger.debug(f"Validating source account: {account_number}")
        source_acc = Account.objects.filter(account_number=account_number).first()
        if not source_acc:
            logger.warning(f"Source account not found: {account_number}")
            return Response({"error":"Source account not found"},status=status.HTTP_404_NOT_FOUND)

        if source_acc.is_active == False:
            logger.warning(f"Source account not active: {account_number}")
            return Response({"error":"Source account not active"}, status=status.HTTP_400_BAD_REQUEST)
       
        # validate if it belongs to the user
        try:
            authorize_user(user, source_acc)
        except PermissionDenied as e:
            logger.warning(f"Authorization failed for user {user.id} on account {source_acc.id}")
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)

        # validate destination account
        logger.debug(f"Validating destination account: {destination_account_number}")
        dest_acc = Account.objects.filter(account_number=destination_account_number).first()
        if not dest_acc:
            logger.warning(f"Destination account not found: {destination_account_number}")
            return Response({"error":"Destination account not found"},status=status.HTTP_404_NOT_FOUND)
        
        if dest_acc.is_active == False:
            logger.warning(f"Destination account not active: {destination_account_number}")
            return Response({"error":"Destination account not active"}, status=status.HTTP_400_BAD_REQUEST)
        
        # validate inputs
        if not amount or amount <= 0:
            logger.warning(f"Invalid amount: {amount}")
            return Response({"error":"Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)
        
        amount = Decimal(str(amount))
        logger.debug(f"Amount validated: {amount}")

        fee = calculate_transaction_fee(amount, transaction_type)
        logger.debug(f"Transaction fee calculated: {fee}")

        fraud_log = None
        fraud_data = None

        try:
            fraud_response = requests.post(
                'http://localhost:8080/api/v1.0/fraud/check',

                json = {
                    'amount':float(amount),
                    'account_id':source_acc.account_number,
                    'destination_account':dest_acc.account_number,
                    'transaction_type':transaction_type
                },
                timeout=0.1 
            )

            fraud_data = fraud_response.json()

            # save the response from the fr
            from fraud_service.models import FraudDetection
            fraud_log = FraudDetection.objects.create(
                account_number = source_acc.account_number,
                amount = amount,
                risk_score = fraud_data.get('risk_score',0),
                decision = fraud_data.get('decision','APPROVE'),
                reason = fraud_data.get('reason',''),
                flags = fraud_data.get('flags',[]),
                processing_time_ms = int(fraud_data.get('processing_time_ms','0ms').replace('ms',''))                       
            )
            logger.info(f'fraud log created and saved {fraud_data}')

            if fraud_data['decision'] == 'BLOCK':
                return Response({
                    "error":fraud_data['reason']
                }, status=status.HTTP_403_FORBIDDEN)

        
        except Exception as e:
            logger.error(f"Error checking fraud detection: {str(e)}")
            #update failed metrics counnt for fraud
            fraud_detection_failed_total.labels(
                fraud_type=transaction_type,
                failure_reason='service_unavailable'
            ).inc()
            pass
        
        try:
            # check available balance
            logger.debug(f"Checking available balance")
            check_available_balance(source_acc, amount, fee)
            
            # validate business rules
            logger.debug(f"Validating business rules")
            validate_business_rules(amount, transaction_type, source_acc, dest_acc)
            
            
            # validate transaction limits
            logger.debug(f"Validating transaction limits")
            validate_limits(source_acc, amount, transaction_type)
            
            
            with transaction.atomic():
                logger.debug(f"Entering atomic transaction block")
                # check if the idempotency key exists
                trans = Transaction.objects.select_for_update().filter(
                    idempotency_key = idempotency_Key
                ).first()

                if trans:
                    logger.debug(f"Idempotency key found: {trans.id}, status: {trans.trans_status}")
                    
                    if trans.trans_status == TransactionStatus.COMPLETED:
                        logger.info(f"Duplicate transaction request, already completed: {trans.id}")
                        return Response({"message":"Transaction already completed",
                                         "tras_ref":trans.transaction_ref                         
                                         }, status=status.HTTP_200_OK)
                    if trans.trans_status in (TransactionStatus.PENDING,TransactionStatus.PROCESSING):
                        logger.info(f"Transaction still processing: {trans.id}")
                        return Response({
                            "message": "Transaction is still processing",
                            "transaction_id": trans.id,
                            "status": trans.trans_status
                        }, status=status.HTTP_409_CONFLICT)

                    if trans.trans_status == TransactionStatus.FAILED:
                        if trans.retry_count < 3:
                            logger.info(f"Retrying failed transaction: {trans.id}, retry_count: {trans.retry_count}")
                            trans.trans_status = TransactionStatus.PENDING
                            trans.retry_count += 1
                            trans.save()
                            return Response({
                                "message": "Transaction failed, retrying",
                                "transaction_id": trans.id,
                                "status": trans.trans_status
                            }, status=status.HTTP_409_CONFLICT)
                        else:
                            logger.warning(f"Transaction max retries exceeded: {trans.id}")
                            return Response({
                                "message": "Transaction failed, max retries reached",
                                "transaction_id": trans.id,
                                "status": trans.trans_status
                            }, status=status.HTTP_409_CONFLICT)
                
                # create transaction object
                logger.debug(f"Creating transaction object")
                trans = Transaction.objects.create(
                    source_account=source_acc,
                    destination_account=dest_acc,
                    amount=amount,
                    transaction_type=transaction_type,
                    idempotency_key=idempotency_Key,
                    trans_status=TransactionStatus.PENDING,
                    metadata={'request_params': request.data},
                    initiated_by=user,
                    transaction_ref=generate_transaction_ref(),
                    fee = fee
                )
                logger.debug(f"Transaction object created: {trans.id}")

                if fraud_log:
                    fraud_log.transaction = trans
                    fraud_log.save(update_fields=['transaction'])
                
                # execute transaction
                logger.debug(f"Executing transaction")
                executed_transaction = execute_transaction(trans)
                
                logger.info(f"Transaction completed successfully: {executed_transaction.id}")
                return Response({
                    "message": "Transaction successful",
                    "transaction_id": executed_transaction.id,
                    "transaction_ref": executed_transaction.transaction_ref,
                    "fraud_check": fraud_data['reason'] if fraud_data else None
                }, status=status.HTTP_200_OK)
                
        except (ValidationError, PermissionDenied, LimitExceeded) as e:
            logger.error(f"Validation error in transaction: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Internal transfer error for transaction: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class HandleTransactionHistory(APIView):
    
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get(self, request, account_number):
        user = request.user
        
        # Get and validate account
        account = get_object_or_404(Account, account_number=account_number)
        
        try:
            authorize_user(user, account)
        except PermissionDenied as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Build optimized query
        # Use select_related to avoid N+1 queries
        queryset = Transaction.objects.filter(
            Q(source_account=account) | Q(destination_account=account)
        ).select_related(
            'source_account',
            'destination_account',
        ).only(
            'id',
            'transaction_ref',
            'transaction_type',
            'trans_status',
            'amount',
            'currency',
            'fee',
            'description',
            'external_ref',
            'created_at',
            'completed_at',
            'metadata',
            'source_account_id',
            'destination_account_id',
            'source_account__account_number',
            'destination_account__account_number',
        ).order_by('-created_at', '-id')  # Consistent ordering
        
        # Apply filters
        queryset = self._apply_filters(queryset, request)
        
        # Paginate results
        paginator = CursorPagination(page_size=50, max_page_size=1)
        results, next_cursor, previous_cursor, has_more = paginator.paginate_queryset(
            queryset, 
            request
        )
        
        # Serialize data
        serializer = TransactionSerializer(
            results, 
            many=True,
            context={'account': account}
        )
        
        response_data = {
            'count': len(results),
            'next': next_cursor,
            'previous': previous_cursor,
            'has_more': has_more,
            'results': serializer.data,
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    def _apply_filters(self, queryset, request):
        """Apply query filters from request parameters"""
        
        # Transaction type filter
        transaction_type = request.GET.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Status filter
        trans_status = request.GET.get('status')
        if trans_status:
            queryset = queryset.filter(trans_status=trans_status)
        
        # Date range filters
        start_date = request.GET.get('start_date')
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                queryset = queryset.filter(created_at__gte=start_dt)
            except ValueError:
                pass
        
        end_date = request.GET.get('end_date')
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                queryset = queryset.filter(created_at__lte=end_dt)
            except ValueError:
                pass
        
        # Amount range filters
        min_amount = request.GET.get('min_amount')
        if min_amount:
            try:
                queryset = queryset.filter(amount__gte=Decimal(min_amount))
            except (ValueError, TypeError):
                pass
        
        max_amount = request.GET.get('max_amount')
        if max_amount:
            try:
                queryset = queryset.filter(amount__lte=Decimal(max_amount))
            except (ValueError, TypeError):
                pass
        
        # Search in description or reference
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(transaction_ref__icontains=search) |
                Q(external_ref__icontains=search)
            )
        
        return queryset

