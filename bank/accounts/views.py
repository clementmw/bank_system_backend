from django.shortcuts import render
from .models import *
from .serializers import *
from .utility import *
# from .tasks import *
from .permissions import *
from django.http import HttpResponse
from auth_service.models import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated,BasePermission
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Sum
from decimal import Decimal
from .metrics import *
from .documentation import v1


#getorcreate

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)



class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return request.user.role and request.user.role.role_name == "Customer"

class AccountView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        customer = CustomerProfile.objects.get(user=request.user)
        accounts = Account.objects.filter(customer=customer).order_by('-is_primary')

        serializer = AccountSerializer(accounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self,request):
        try:
            data = request.data
            user = request.user
            currency = data.get('currency', 'KES')
            account_type = data.get('account_type')
            if not account_type:
                return Response({"error": "Account type is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            customer = CustomerProfile.objects.get(user = user)

            account_type = get_object_or_404(AccountType, name = account_type)

            # check if customer verification status in kyc
            try:
                KycProfile.objects.filter(user=user, verification_status="VERIFIED")
            except Exception as e:
                logger.error(f"Customer {user.username} is not verified for account opening {e}")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            # check if customer has any account in relation to the user
            account = Account.objects.filter(customer=customer)
            is_primary = True
            if account:
                is_primary = False

            with transaction.atomic():
                # check if there is any account in relation to the user 
                account = Account.objects.create(
                    customer=customer,
                    account_type=account_type,
                    currency=currency,
                    balance=0.0
                )
                account.account_number = generate_account_number()
                account.status = "PENDING_APPROVAL" 
                account.is_primary = is_primary
                account.is_joint_account = False
                account.allow_debit = False
                account.allow_credit = False
                account.is_active = False
                account.save()
                accounts_created_total.inc()

                

                # create an account limit for the account
                # diffrent accounttypes have diffrent liits
                if account_type.name == "SAVINGS":
                    AccountLimit.objects.create(
                        account=account,
                        daily_debit_limit=100000,
                        daily_credit_limit=100000,
                        daily_transaction_count_limit=50,
                        single_transaction_debit_limit=100000,
                        single_transaction_credit_limit=100000,
                        monthly_debit_limit=1000000,
                        monthly_credit_limit=1000000,
                    )
                if account_type.name == "FIXED_DEPOSIT":
                    AccountLimit.objects.create(
                        account=account,
                        daily_debit_limit=100000,
                        daily_credit_limit=100000,
                        daily_transaction_count_limit=50,
                        single_transaction_debit_limit=100000,
                        single_transaction_credit_limit=100000,
                        monthly_debit_limit=1000000,
                        monthly_credit_limit=1000000,
                    )
                if account_type.name == "BUSINESS":
                    AccountLimit.objects.create(
                        account=account,
                        daily_debit_limit=1000000,
                        daily_credit_limit=1000000,
                        daily_transaction_count_limit=100,
                        single_transaction_debit_limit=1000000,
                        single_transaction_credit_limit=1000000,
                        monthly_debit_limit=10000000,
                        monthly_credit_limit=10000000,
                    )

                
                return Response({
                    "message": "Account created successfully",
                    "account_number": account.account_number,
                    "account_type": account.account_type.name,
                    "currency": account.currency,
                    "balance": account.balance,
                    "status": account.status,
                }, status=status.HTTP_201_CREATED)

        
        except Exception as e:
            accounts_creation_failed_total.inc()
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ManageAccounts(APIView):
    permission_classes = [IsAuthenticated, HasAccountPermission]

    def get(self,request):
        """
        bank staff can view account details for the customers
        """

        user = request.user

        try:
            get_account = Account.objects.all().order_by('-created_at')
            # filters
            acc_status = request.query_params.get('status')
            account_type = request.query_params.get('account_type')
            opened_at = request.query_params.get('opened_at')
            currency = request.query_params.get('currency')
            search = request.query_params.get('search')

            
            if acc_status:
                get_account = get_account.filter(status=acc_status)
            
            if account_type:
                get_account = get_account.filter(account_type__name=account_type)

            if opened_at:
                get_account = get_account.filter(opened_at__date=opened_at)

            if currency:
                get_account = get_account.filter(currency=currency)
            
            if search:
                get_account = get_account.filter(
                    Q(account_number__icontains=search) |
                    Q(customer__user__first_name__icontains=search) |
                    Q(customer__user__last_name__icontains=search) |
                    Q(customer__user__email__icontains=search)
                )

            pagination = CustomPagination()
            paginated_accounts = pagination.paginate_queryset(get_account, request)
            serializer = AccountSerializer(paginated_accounts, many=True)
            return pagination.get_paginated_response(serializer.data)

        except Exception as e:
            return Response ({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    
class ApproveAccounts(APIView):
    permission_classes = [IsAuthenticated, HasAccountPermission]
    
    @v1.approve_account_docs()
    def post(self,request,account_id):
            
        """
        bank staff approve or reject account opening
        """

        user = request.user
       
        try:
            # get the account
            account = Account.objects.get(id=account_id)

            # ensure it has a pending approval status
            if account.status != "PENDING_APPROVAL":
                return Response({"error": "Account is not pending approval",
                                 "account_state": account.status
                                 }, status=status.HTTP_400_BAD_REQUEST)
            
            
            # activvate acc
            account.status = "ACTIVE"
            account.approved_at = timezone.now()
            account.approved_by = user
            account.is_active = True
            account.allow_debit = True
            account.allow_credit = True
            account.save()

            # update metrics
            accounts_approved_total.inc()

            # celery task for email notification
            # send_account_approved.delay(account.id, action)

            return Response({
                "message": "Account approved successfully",
                "approved_by":user.email,
                "role":user.role.role_name
                             
                }, status=status.HTTP_200_OK)
        
        except Exception as e:

            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RejectAccounts(APIView):
    permission_classes = [IsAuthenticated, HasAccountPermission]

    @v1.reject_account_docs()
    def post(self, request, account_id):

        """
        bank staff reject account opening
        """

        user = request.user
        
        # Validate request data
        reason = request.data.get('reason', '').strip()
        
        if not reason:
            return Response(
                {
                    "error": "Rejection reason is required",
                    "message": "Please provide a detailed reason for rejecting this account"
                },
                status=status.HTTP_400_BAD_REQUEST
                )
        try:
            # get the account
            account = Account.objects.get(id=account_id)

            # ensure it has a pending approval status
            if account.status != "PENDING_APPROVAL":
                return Response(
                    {"error": "Account is not pending approval",
                     "account_state": account.status
                     
                     }, status=status.HTTP_400_BAD_REQUEST)

            # check if account is active
            if not account.is_active:
                return Response({"error": "Account is not active"}, status=status.HTTP_400_BAD_REQUEST)

            # activvate acc
            account.status = 'CLOSED'
            account.closed_by = request.user
            account.closed_at = timezone.now()
            account.closure_reason = reason

            account.is_active = False
            account.save()

            # update metrics
            accounts_rejected_total.inc()

            # celery task for email notification
            # send_account_rejected.delay(account.id, action)

            return Response({"message": "Account rejected successfully",
                             "closed_by":user.email,
                             "role":user.role.role_name
                             }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error rejecting account: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



        

class FreezeAccounts(APIView):
    permission_classes = [IsAuthenticated, HasAccountPermission]

    def post(self, request, account_id):

        """
        bank staff temporary freeze account can be frau legal etc
        """

        user = request.user
        data = request.data
        reason = data.get('reason', '').strip()

        if not reason:
            return Response(
                {
                    "error": "Freeze reason is required",
                    "message": "Please provide a detailed reason for freezing this account"
                },
                status=status.HTTP_400_BAD_REQUEST
                )

        try:

            get_acc = get_object_or_404(Account, id = account_id)
            # ensure account is active
            if not get_acc.is_active:
                return Response({"error": "Account is not active"}, status=status.HTTP_400_BAD_REQUEST)
        

            get_acc.status = "FROZEN"
            get_acc.closed_by = user
            get_acc.closed_at = timezone.now()
            get_acc.closure_reason = reason
            get_acc.allow_debit= False
            get_acc.allow_credit = False
            get_acc.save()

            # customer notification
            # send_account_frozen.delay(get_acc.id, reason)

            

            return Response({"message": "Account frozen successfully",
                             "closed_by":user.email,
                             "role":user.role.role_name
                             }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HandleUnfreezingAccounts(APIView):
    permission_classes = [IsAuthenticated, HasAccountPermission]

    def post(self, request, account_id):

        """
        bank staff unfreeze account
        """

        user = request.user

        try:

            get_acc = get_object_or_404(Account, id = account_id)

            # confirm freeze reason is resolved

            get_acc.status = "ACTIVE"
            get_acc.closed_by = None
            get_acc.closed_at = None
            get_acc.closure_reason = ""
            get_acc.allow_debit= True
            get_acc.allow_credit = True
            get_acc.is_active = True
            get_acc.approved_by = user
            get_acc.save()

            # notofy client 
            # send_account_unfrozen.delay(get_acc.id)


        
        except Exception as e:
            logger.error(f"Error unfreezing account: {str(e)}")
            return Response ({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HandleRequestCloseAccount(APIView):
    """
    client request closure of an account 
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    def post(self,request,account_id):
        pass


class handleCloseRequest(APIView):
    """
    bank staff handle closure for account request
    """
    permission_classes = [IsAuthenticated, HasAccountPermission]
    def post(self, request, account_id):
        pass


# handle limit mananagement

class AccountLimitView(APIView):
    permission_classes = [IsAuthenticated, HasAccountPermission]

    """
    bank staff and customer can see the account limit for a specific account
    """

    def get(self, request,account_id):
        try:
            account = get_object_or_404(Account, id=account_id)

            account_limit = get_object_or_404(AccountLimit,account=account)
            # limit requests
            limit_request = AccountLimitOverrideRequest.objects.filter(account = account)
            
            serializer = AccountLimitSerializer(account_limit)
            return Response({
                "account_number":account.account_number,
                "limits":serializer.data,
                "request":LimitOverrideRequestSerializer(limit_request, many = True).data if limit_request else None
                
                }, status=status.HTTP_200_OK)

        except AccountLimit.DoesNotExist:
            return Response({"error": "Account limit not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving account limit: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, account_id):
        """
        Bank staff can set new account limits or reject override requests.
        """
        user = request.user
        data = request.data
        try:
            account = get_object_or_404(Account, id=account_id)
            account_limit = get_object_or_404(AccountLimit, account=account)
            
            # The action can be "APPROVE" or "REJECT"
            action = data.get('action', '').upper()
            reason = data.get('reason', '').strip()

            if not action or action not in ["APPROVE", "REJECT"]:
                return Response(
                    {"error": "Invalid action", "message": "Action must be either 'APPROVE' or 'REJECT'"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the related override request, if it exists
            try:
                req = AccountLimitOverrideRequest.objects.get(account=account)
            except AccountLimitOverrideRequest.DoesNotExist:
                return Response(
                    {"error": "No override request found for this account"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with transaction.atomic():
                if action == "APPROVE":
                    if not reason:
                        return Response(
                            {"error": "Reason required for approval"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    serializer = AccountLimitSerializer(account_limit, data=request.data, partial=True)
                    if serializer.is_valid():
                        account_limit.limit_override_approved_by = user
                        account_limit.limit_override_reason = reason
                        serializer.save()

                        req.status = "APPROVED"
                        req.save()

                        # Optional: send notification
                        # limit_change.delay(account.id)

                        return Response({
                            "message": "Account limit updated successfully",
                            "account_number": account.account_number,
                            "limits": serializer.data
                        }, status=status.HTTP_200_OK)
                    
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                elif action == "REJECT":
                    if not reason:
                        return Response(
                            {"error": "Reason required for rejection"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    req.status = "REJECTED"
                    req.save()
                    account_limit.limit_override_reason = reason
                    account_limit.limit_override_approved_by= user
                    account_limit.save()

                    return Response({
                        "message": "Account limit override request rejected",
                        "account_number": account.account_number,
                        "request_status": req.status,
                        "reason": reason
                    }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error updating account limit: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HandleRequestOverride(APIView):
    """
    customer can request for limit override
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self,request,account_id):
        """
        get the status of the limit if applicable

        """
        try:
            user = request.user

            account = get_object_or_404(Account, id=account_id)
            acc_lmt = get_object_or_404(AccountLimit, account = account)

            account_limit = get_object_or_404(AccountLimitOverrideRequest, account=account)

            return Response({
                "account_number": account.account_number,
                "status": account_limit.status,
                "reason": acc_lmt.limit_override_reason if acc_lmt.limit_override_reason else None,

            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response ({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, account_id):
        try:
            user = request.user
            data = request.data
            account = get_object_or_404(Account, id=account_id)


            reason = data.get('reason', '').strip()
            daily_debit = data.get('requested_daily_debit')
            daily_credit = data.get('requested_daily_credit')
            
            # Validation
            if not daily_debit or not daily_credit:
                return Response(
                    {"error": "Daily debit and credit limits are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not reason:
                return Response(
                    {
                        "error": "Limit override reason is required",
                        "message": "Please provide a detailed reason for requesting overriding this account limit"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # create a limit override request
            override_request = AccountLimitOverrideRequest.objects.create(
                account=account,
                requested_by=user,
                reason=reason,
                requested_daily_debit_limit=daily_debit,
                requested_daily_credit_limit=daily_credit
            )


            # notify bank staff for approval
            # notify_limit_override.delay(override_request.id)

            return Response({
                "message": "Limit override request submitted successfully",
                "request_id": override_request.id,
                "status": override_request.status
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating limit override request: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

class HandleAccountHold(APIView):
    """
    staff can get all accounts on hhold with the respecctive reasons 
    """
    permission_classes = [IsAuthenticated, HasAccountPermission]

    def get(self, request, account_id):
        try:
            account = get_object_or_404(Account, id=account_id)

            # get all holds for this account
            holds = AccountHold.objects.filter(account=account)

            # filters and searches
            hold_type = request.query_params.get('hold_type')
            is_released = request.query_params.get('is_released')
            search = request.query_params.get('search')

            if hold_type:
                holds = holds.filter(hold_type=hold_type)
            
            if is_released is not None:
                holds = holds.filter(is_released=is_released.lower() == 'true')
            if search:
                holds = holds.filter(
                    Q(reason__icontains=search) |
                    Q(reference_id__icontains=search) |
                    Q(placed_by__username__icontains=search) |
                    Q(released_by__username__icontains=search) |
                    Q(account__account_number__icontains=search)
                )
            pagination = CustomPagination()
            pagin_respo = pagination.paginate_queryset(holds, request)
            
            serializer = AccountHoldSerializer(pagin_respo, many=True)

            return pagination.get_paginated_response(serializer.data)

        except Exception as e:
            logger.error(f"Error retrieving account holds: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self,request,account_id):
        """
        staff can place a hold on an account
        """
        user = request.user
        data = request.data

        try:

            hold_type = data.get('hold_type')
            amount = data.get('amount')
            reason = data.get('reason', '').strip()
            expiry_date = data.get('expiry_date')

            # Validation
            if not hold_type or not amount or not reason :
                return Response(
                    {"error": "All fields are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            with transaction.atomic():
                account = Account.objects.select_for_update().get(id=account_id)
                #check available balance and validate the amount is there and then subtract it temporarry
                if account.balance < Decimal(amount):
                    return Response(
                        {"error": "Insufficient balance to place this hold"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                reference_id = generate_ref_id()
                hold = AccountHold.objects.create(
                    account=account,
                    hold_type=hold_type,
                    amount=amount,
                    reason=reason,
                    reference_id=reference_id,
                    placed_by=user,
                    expiry_date=expiry_date
                )

                account.available_balance -= Decimal(amount)
                account.save()

                return Response({
                    "message": "Account hold placed successfully",
                    "hold_id": hold.id,
                    "account_number": account.account_number,
                    "hold_type": hold.hold_type,
                    "amount": hold.amount,
                    "reason": hold.reason,
                    "reference_id": hold.reference_id,
                }, status=status.HTTP_201_CREATED)

                # create a notification for client 
                #accounthold.delay(hold.id)

        except Exception as e:
            logger.error(f"Error placing account hold: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# task  beneficially and joint account views


















































































# class HandleAccountStatement(APIView):
#     """
#     Handle account statement retrieval and generation
#     """
#     permission_classes = [IsAuthenticated, IsCustomer]  

#     def get(self, request):
#         try:
#             # Get query parameters (not request.data for GET)
#             account_number = request.query_params.get('account_number')
#             statement_type = request.query_params.get('statement_type', 'MONTHLY')
#             start_date = request.query_params.get('start_date')
#             end_date = request.query_params.get('end_date')

#             # Validation
#             if not account_number:
#                 return Response(
#                     {"error": "Account number is required"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             # Get customer and account
#             customer = CustomerProfile.objects.get(user=request.user)
#             account = Account.objects.get(
#                 account_number=account_number, 
#                 customer=customer,
#                 status='ACTIVE'
#             )

#             # Build query filters
#             filters = Q(account=account, statement_type=statement_type)
            
#             if start_date and end_date:
#                 # Parse dates
#                 start = datetime.strptime(start_date, '%Y-%m-%d').date()
#                 end = datetime.strptime(end_date, '%Y-%m-%d').date()
#                 filters &= Q(period_start__gte=start, period_end__lte=end)

#             # Get statements
#             statements = AccountStatement.objects.filter(filters).order_by('-period_end')

#             serializer = AccountStatementSerializer(statements, many=True)
#             return Response({
#                 "count": statements.count(),
#                 "statements": serializer.data
#             }, status=status.HTTP_200_OK)

#         except CustomerProfile.DoesNotExist:
#             return Response(
#                 {"error": "Customer profile not found"}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         except Account.DoesNotExist:
#             return Response(
#                 {"error": "Account not found or not active"}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         except ValueError as e:
#             return Response(
#                 {"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}"}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         except Exception as e:
#             return Response(
#                 {"error": f"An error occurred: {str(e)}"}, 
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     def post(self, request):
#         """
#         POST method for generating new statement on-demand
#         """
#         try:
#             data = request.data
#             account_number = data.get('account_number')
#             statement_type = data.get('statement_type', 'ON_DEMAND')
#             start_date = data.get('start_date')
#             end_date = data.get('end_date')

#             # Validation
#             if not account_number:
#                 return Response(
#                     {"error": "Account number is required"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             if not start_date or not end_date:
#                 return Response(
#                     {"error": "Start date and end date are required"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             # Parse dates
#             start = datetime.strptime(start_date, '%Y-%m-%d').date()
#             end = datetime.strptime(end_date, '%Y-%m-%d').date()

#             # Validate date range
#             if start >= end:
#                 return Response(
#                     {"error": "Start date must be before end date"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             # Max 1 year range for on-demand statements
#             if (end - start).days > 365:
#                 return Response(
#                     {"error": "Date range cannot exceed 1 year"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             # Get customer and account
#             customer = CustomerProfile.objects.get(user=request.user)
#             account = Account.objects.get(
#                 account_number=account_number, 
#                 customer=customer,
#                 status='ACTIVE'
#             )

#             # Check if statement already exists
#             existing = AccountStatement.objects.filter(
#                 account=account,
#                 statement_type=statement_type,
#                 period_start=start,
#                 period_end=end
#             ).first()

#             if existing:
#                 # Return existing statement
#                 serializer = AccountStatementSerializer(existing)
#                 return Response({
#                     "message": "Statement already exists",
#                     "statement": serializer.data
#                 }, status=status.HTTP_200_OK)

#             # Generate new statement
#             statement = generate_account_statement(
#                 account=account,
#                 statement_type=statement_type,
#                 period_start=start,
#                 period_end=end,
#                 generated_by=request.user
#             )

#             # Trigger PDF generation in background
#             generate_statement_pdf.delay(statement.id)

#             serializer = AccountStatementSerializer(statement)
#             return Response({
#                 "message": "Statement generated successfully",
#                 "statement": serializer.data
#             }, status=status.HTTP_201_CREATED)

#         except CustomerProfile.DoesNotExist:
#             return Response(
#                 {"error": "Customer profile not found"}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         except Account.DoesNotExist:
#             return Response(
#                 {"error": "Account not found or not active"}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         except ValueError as e:
#             return Response(
#                 {"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}"}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         except Exception as e:
#             return Response(
#                 {"error": f"An error occurred: {str(e)}"}, 
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )




