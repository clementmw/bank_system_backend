from django.shortcuts import render
from .models import *
from .serializers import *
from .utility import *
from .tasks import *
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
            kystatus = KycProfile.objects.get(user=user, verification_status="APPROVED")
            if not kystatus:
                return Response({"error": "Customer is not verified"}, status=status.HTTP_400_BAD_REQUEST)

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
                account.status = "ACTIVE"
                account.is_primary = is_primary
                account.save()
                

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




