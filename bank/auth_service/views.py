# will handle all authentication here .

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import *
from .models import *
from .task import *
from rest_framework.permissions import IsAuthenticated,BasePermission
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from django.db import transaction
import os
import re
from django.utils import timezone
from .permissions import CanManageEmployees


logger = logging.getLogger(__name__)


def serialize_full_user(user):
    # Serialize basic user data
    user_data = UserSerializer(user).data
    
    # Get the role name from the ForeignKey relationship
    role_name = user.role.role_name  
    
    # Map role names to their respective profile serializers
    profile_serializers = {
        'STAFF': EmployeeProfileSerializer,
        'CUSTOMER': CustomerProfileSerializer,
        'ADMIN': EmployeeProfileSerializer,  # Assuming admin uses employee profile
    }
    
    # Get the appropriate serializer class for the role
    serializer_class = profile_serializers.get(role_name)
    
    if serializer_class:
        # Get the profile object based on role
        profile_obj = None
        if role_name == 'CUSTOMER':
            profile_obj = getattr(user, 'customer_profile', None)
        elif role_name in ['STAFF', 'ADMIN']:
            profile_obj = getattr(user, 'employee_profile', None)
        
        # Serialize profile data if exists
        if profile_obj:
            profile_data = serializer_class(profile_obj).data
            profile_data.pop('user', None)  # Remove nested user if exists
            user_data['profile'] = profile_data
        else:
            user_data['profile'] = None
    
    user_data['role_name'] = role_name
    
    return user_data



class RegisterView(APIView):

    def post(self,request):
        try:
            data = request.data

            email = data.get('email').lower() #for consistency
            password = data.get('password')
            phone_number = data.get('phone_number')
            address = data.get('address')

            if not email or not password or not phone_number:
                return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Block superuser/staff emails from being registered
            privileged_user = User.objects.filter(email__iexact=email, is_superuser=True).exists() \
                                or User.objects.filter(email__iexact=email, is_staff=True).exists()
            if privileged_user:
                # log the request
                logger.warning(f"Attempted registration with privileged email: {email} at {request.META.get('REMOTE_ADDR')}")
                
                return Response(
                    {"error": "Invalid email or password"},status=status.HTTP_401_UNAUTHORIZED)
            # confrim if email already exists
            if User.objects.filter(email=email).exists():
                return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)


            role = Role.objects.get(name="CUSTOMER")  # default role is customer
            
            with transaction.atomic():               
                serializer = UserSerializer(data={**request.data, "email":email, "role": role.id})
                if serializer.is_valid():
                    user = serializer.save()
                    user.is_active = False  # Deactivate user until email is verified
                    user.save()
                
                    
                    # Create CustomerProfile
                    CustomerProfile.objects.create(
                        user=user,
                        customer_id=generate_customer_id(),
                        phone_number=phone_number,
                        address=address
                    )
                    
                    # create kyc instance
                    KycProfile.objects.create(
                        user = user,
                        verification_status = "INCOMPLETE"
                    )
                    
                    logger.info(f"New user registered: {email} with role {role.name}")

                    # trigger email verification task
                    send_verification_email(user.id)
                    
                    return Response(
                        {
                            'message': 'User registered successfully',
                            'role':user.role.name,
                            # 'user': serialize_full_user(user)
                         },
                         
                        status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class VerifyEmailView(APIView):

    def get(self, request):
        try:
            uid = request.query_params.get("uid")
            token = request.query_params.get("token")

            if not uid or not token:
                return Response({"error": "Invalid verification link"},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(id=uid)

                if user.verify_email(token):
                    # send onboarding email
                    # send_onboarding_email.delay(user.id)

                    return Response({"message": "Email verified successfully"},status=status.HTTP_200_OK)
                else:
                    return Response({"error": "Invalid or expired token"},
                                    status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({"error": "User not found"},
                                status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerLoginView(APIView):

    def post(self, request):
        try:
            data = request.data
            email = data.get("email").lower()
            password = data.get("password")
            customer_id = data.get("customer_id")

            if not email or not password:
                return Response({"error": "Email and password are required"},status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(email=email) #might opt to login with customerid
                print(user.is_active)


                if not user.check_password(password):
                    return Response({"error": "Invalid email or password"},
                                    status=status.HTTP_401_UNAUTHORIZED)

                if user.role.name != "CUSTOMER":
                    return Response({"error": "Access denied. Not a customer."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)

                if not user.is_active:
                    return Response({"error": "Account is inactive. Please verify your email."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)

                # check kyc verification status

                # if  user.kyc_profile.verification_status == "PENDING":
                #     return Response({"error": "Please upload KYC."}, status=status.HTTP_403_FORBIDDEN)
                
                # if not user.kyc_profile.verification_status == "VERIFIED":
                #     return Response({"error": "Account is not verified. Please upload KYC."}, 
                #                     status=status.HTTP_403_FORBIDDEN)

                refresh = RefreshToken.for_user(user)
                user_data = serialize_full_user(user)

                return Response({
                    "message": "Login successful",
                    "user": user_data,
                    "kyc_status": user.kyc_profile.verification_status,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }, status=status.HTTP_200_OK)

            except User.DoesNotExist:
                return Response({"error": "Invalid email or password"},status=status.HTTP_401_UNAUTHORIZED)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ForgetpasswordView(APIView):
    pass

class ConfirmOtpView(APIView):
    pass

class ResetPasswordView(APIView):
    pass

class handleKYC(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        """
        customer can see their upploed data
        """

    def post(self, request):
        try:
            user = request.user

            # Ensure user is customer
            if user.role.name != "CUSTOMER":
                return Response({"error": "Access for KYC denied"}, status=status.HTTP_403_FORBIDDEN)

            # Extract profile data
            id_no = request.data.get("id_no")
            next_of_kin = request.data.get('kin_name')
            next_of_kin_contact = request.data.get('kin_contact')
            occupation = request.data.get('occupation')
            date_of_birth = request.data.get('dob')
            address = request.data.get('address')

            print(request.data)

            # Extract documents data
            documents_data = self._extract_documents_data(request)

            if not documents_data:
                return Response({"error": "At least one document is required"}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # Update customer profile
                customer_profile = CustomerProfile.objects.get(user=user)
                customer_profile.national_id = id_no
                customer_profile.next_of_kin_name = next_of_kin
                customer_profile.next_of_kin_contact = next_of_kin_contact
                customer_profile.occupation = occupation
                customer_profile.date_of_birth = date_of_birth
                customer_profile.address = address
                customer_profile.save()

                # Create or get KYC profile
                kyc_profile= KycProfile.objects.get(
                    user=user,
                )

                # Handle document uploads
                saved_documents = []
                errors = []

                for doc_data in documents_data:
                    document_type = doc_data['document_type']
                    file_obj = doc_data['file']
                    # document_number = doc_data.get('document_number')
                    # expiry_date = doc_data.get('expiry_date')

                    error = self._validate_document(file_obj, document_type)
                    if error:
                        errors.append({
                            "document_type": document_type,
                            "error": error
                        })
                        continue

                    try:
                        # Create or update KYC document
                        kyc_doc, created = KycDocument.objects.update_or_create(
                            kyc_profile=kyc_profile,
                            document_type=document_type,
                            defaults={
                                'document_upload': file_obj,
                                # 'document_number': document_number,
                                # 'expiry_date': expiry_date,
                                'status': 'PENDING'
                            }
                        )
                        
                        saved_documents.append({
                            "document_type": document_type,
                            "file_name": file_obj.name,
                            # "document_number": document_number,
                            "status": "uploaded"
                        })

                    except Exception as e:
                        errors.append({
                            'document_type': document_type,
                            'file_name': file_obj.name,
                            'error': str(e)
                        })

                # Update KYC profile status if documents were uploaded
                if saved_documents:
                    kyc_profile.verification_status = 'PENDING'
                    kyc_profile.save()

                # Prepare response
                if errors and not saved_documents:
                    return Response({
                        "error": "All document uploads failed",
                        "details": errors
                    }, status=status.HTTP_400_BAD_REQUEST)

                response_data = {
                    "message": "KYC information submitted successfully",
                    "kyc_profile_id": kyc_profile.id,
                    "saved_documents": saved_documents,
                    "profile_updated": True,
                    "kyc_status": kyc_profile.verification_status
                }

                if errors:
                    response_data["partial_errors"] = errors
                    response_data["message"] = "KYC submitted with some errors"

                # Notify admin
                # send_new_kyc.delay(kyc_profile.id)

                return Response(response_data, status=status.HTTP_200_OK)

        except CustomerProfile.DoesNotExist:
            return Response({"error": "Customer profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _extract_documents_data(self, request):
        """Extract documents data from request"""
        documents_data = []
        
        # Method 1: Array format
        document_types = request.data.getlist('document_types')
        document_files = request.FILES.getlist('documents')
        # expiry_dates = request.data.getlist('expiry_dates')
        
        if document_types and document_files and len(document_types) == len(document_files):
            for i, (doc_type, file_obj) in enumerate(zip(document_types, document_files)):
                documents_data.append({
                    'document_type': doc_type,
                    'file': file_obj,
                    # 'expiry_date': expiry_dates[i] if i < len(expiry_dates) else None
                })
        else:
            # Method 2: Individual fields
            for key, file_obj in request.FILES.items():
                if key.startswith('document_'):
                    doc_type = key.replace('document_', '').upper()
                    documents_data.append({
                        'document_type': doc_type,
                        'file': file_obj,
                        'expiry_date': request.data.get(f'expiry_date_{doc_type}')
                    })
        
        return documents_data

    def _validate_document(self, file_obj, document_type):
        """Validate document file"""
        if not file_obj or file_obj.size == 0:
            return "No file uploaded or file is empty"
        
        if file_obj.size > 5 * 1024 * 1024:  # 5MB limit
            return "File size exceeds 5MB limit"
        
        # Add file type validation if needed
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
        file_extension = os.path.splitext(file_obj.name)[1].lower()
        if file_extension not in allowed_extensions:
            return f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        return None
    
class handleLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Successfully logged out."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)




#task 1. admin creating account for employesss 2. employees login 3. employees reset their password 4. login 2fa for security 

class StaffLoginView(APIView):

    def post(self, request):
        try:
            data = request.data
            email = data.get("email").lower()
            password = data.get("password")
            customer_id = data.get("customer_id")

            if not email or not password:
                return Response({"error": "Email and password are required"},status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(email=email) #might opt to login with customerid
                print(user.is_active)


                if not user.check_password(password):
                    return Response({"error": "Invalid email or password"},status=status.HTTP_401_UNAUTHORIZED)
                
                # check for staff category
                if user.role.category != "STAFF":
                    return Response({"error": "Access denied. Only staff can login."}, status=status.HTTP_403_FORBIDDEN)


                if not user.is_active:
                    return Response({"error": "Account is inactive. Please verify your email."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)
                
                # session logs for auditing
                session_logs = SessionLogs.objects.create(
                    user=user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    browser_agent=request.META.get('HTTP_USER_AGENT')
                )
                
                

                refresh = RefreshToken.for_user(user)
                user_data = serialize_full_user(user)

                return Response({
                    "message": "Login successful",
                    "user": user_data,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "session_id": str(session_logs.id)
                }, status=status.HTTP_200_OK)

            except User.DoesNotExist:
                return Response({"error": "Invalid email or password"},status=status.HTTP_401_UNAUTHORIZED)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StaffLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh = request.data.get('refresh')
            session_id = request.data.get("session_id")

            if not refresh:
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not session_id:
                return Response({"error": "Session ID is required"}, status=status.HTTP_400_BAD_REQUEST)

            # close staff session log
            if session_id:
                SessionLogs.objects.filter(id=session_id, user=request.user).update(
                    logout_time=timezone.now()
                )

            RefreshToken(refresh).blacklist()
            return Response({"message": "Logged out"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class HandleEmployeeAccount(APIView):
    permission_classes = [IsAuthenticated, CanManageEmployees]

    def post(self, request):
        data = request.data
        email = data.get("email").lower()
        password = generate_temporary_password()
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        role_name = data.get("role_name")  # e.g., "STAFF", "ADMIN"
        department_name = data.get("department_name")  # e.g., "HR", "IT"
        phone_number = data.get("phone_number")
        address = data.get("address")
        employment_type = data.get("employment_type")  # e.g., "FULL_TIME", "PART_TIME"
        job_title = data.get("job_title")
        date_of_hire = data.get("date_of_hire")
        emergecy_person = data.get('contact_name')
        emergency_contact = data.get('emergency_contact')

        if not email or not password or not role_name:
            return Response({"error": "Email, password, and role are required"}, status=status.HTTP_400_BAD_REQUEST)

        
        try:
            try:
                role = Role.objects.get(role_name=role_name)
            except Role.DoesNotExist:
                return Response({"error": f"Role '{role_name}' does not exist"}, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                serializer = UserSerializer(data={
                    "email": email,
                    "password": password,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role.id
                })
                if serializer.is_valid():
                    user = serializer.save()
                    user.is_active = True  # Employees are active by default
                    user.save()

                    # Create EmployeeProfile
                    new_employee = EmployeeProfile.objects.create(
                        user=user,
                        employee_id=generate_employee_id(),
                        phone_number=phone_number,
                        address=address,
                        employment_type=employment_type,
                        job_title=job_title,
                        date_of_hire=date_of_hire,
                        emergency_contact_name = emergecy_person,
                        emergency_contact_phone = emergency_contact
                    )
                    #send the email to the employee
                    try:
                        send_employee_onboarding_email.delay(new_employee.id)
                    except Exception as e:
                        logger.error(f"Failed to send onboarding email to {email}: {str(e)}")

                    logger.info(f"New employee account created: {email} with role {role.role_name}")

                    return Response(
                        {
                            'message': 'Employee account created successfully',
                            'employee_id': new_employee.employee_id,
                            'role': user.role.role_name,
                            'temporary_password': password,
                            # 'user': serialize_full_user(user)
                         },
                        status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response ({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

      