import string
import secrets
from decimal import Decimal
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import pagination
 
def generate_account_number():
    """Generate unique 16-digit account number"""
    number = '1001' + ''.join(secrets.choice(string.digits) for _ in range(12))
    return number

# def generate_account_statement(account, statement_type, period_start, period_end, generated_by=None):
#     from accounts.models import AccountStatement  

#     """
#     Generate account statement with actual transaction data
    
#     Args:
#         account: Account instance
#         statement_type: Type of statement (MONTHLY, QUARTERLY, etc.)
#         period_start: Start date of statement period
#         period_end: End date of statement period
#         generated_by: User who requested the statement (optional)
    
#     Returns:
#         AccountStatement instance
#     """
#     from transactions.models import Transaction  # Import here to avoid circular imports
    
#     # Get opening balance (balance at start of period)
#     # This should be calculated from transactions before period_start
#     opening_balance = calculate_opening_balance(account, period_start)
    
#     # Get all transactions in the period
#     transactions = Transaction.objects.filter(
#         Q(source_account=account) | Q(destination_account=account),
#         transaction_date__gte=period_start,
#         transaction_date__lte=period_end,
#         status__in=['COMPLETED', 'SETTLED']  # Only completed transactions
#     ).order_by('transaction_date')
    
#     # Calculate totals
#     total_credits = Decimal('0.00')
#     total_debits = Decimal('0.00')
    
#     for txn in transactions:
#         if txn.destination_account == account:
#             # Money coming in
#             total_credits += txn.amount
#         elif txn.source_account == account:
#             # Money going out
#             total_debits += txn.amount
    
#     # Calculate closing balance
#     closing_balance = opening_balance + total_credits - total_debits
    
#     # Verify closing balance matches account balance (if end date is today)
#     if period_end == timezone.now().date():
#         if abs(closing_balance - account.balance) > Decimal('0.01'):
#             # Log discrepancy for investigation
#             import logging
#             logger = logging.getLogger(__name__)
#             logger.error(
#                 f"Balance mismatch for account {account.account_number}: "
#                 f"Calculated: {closing_balance}, Actual: {account.balance}"
#             )
    
#     # Create statement
#     statement = AccountStatement.objects.create(
#         account=account,
#         statement_type=statement_type,
#         period_start=period_start,
#         period_end=period_end,
#         opening_balance=opening_balance,
#         closing_balance=closing_balance,
#         total_credits=total_credits,
#         total_debits=total_debits,
#         transaction_count=transactions.count(),
#         generated_by=generated_by,
#     )
    
#     return statement


# def calculate_opening_balance(account, period_start):
#     """
#     Calculate opening balance at the start of the period
    
#     This is the balance before the period_start date
#     """
#     from transactions.models import Transaction
    
#     # Get all transactions before period_start
#     credits = Transaction.objects.filter(
#         destination_account=account,
#         transaction_date__lt=period_start,
#         status__in=['COMPLETED', 'SETTLED']
#     ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
#     debits = Transaction.objects.filter(
#         source_account=account,
#         transaction_date__lt=period_start,
#         status__in=['COMPLETED', 'SETTLED']
#     ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
#     # Opening balance = all credits - all debits before period
#     opening_balance = credits - debits
    
#     return opening_balance


class CustomPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'