# will handle all authentication here .

from django.shortcuts import render,get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from .serializers import *
from .models import *
from .task import *
from .utility import *
from rest_framework.permissions import IsAuthenticated,BasePermission
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
import logging
import os
import re
from django.utils import timezone
from .permissions import *
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
# from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.contrib.auth.hashers import check_password
from accounts.models import Account
from django.contrib.auth.models import update_last_login






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

            # validate password
            password_error = validate_password_strength(password)
            if not password_error[0]:
                return Response({'error': password_error[1]}, status=status.HTTP_400_BAD_REQUEST)


            role = Role.objects.get(category="Customer")  # default role is customer
            
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
                    
                    logger.info(f"New user registered: {email} with role {role.role_name}")

                    # trigger email verification task
                    send_verification_email(user.id)
                    
                    return Response(
                        {
                            'message': 'User registered successfully',
                            'role':user.role.role_name,
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

                if user.role.category != "Customer":
                    return Response({"error": "Access denied. Not a customer."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)

                if not user.is_active:
                    return Response({"error": "Account is inactive. Please verify your email."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)


                update_last_login(None, user)

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
        
class HandleSecurityQuestions(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pass


class ForgetpasswordView(APIView):
    # @method_decorator(ratelimit(key='post:email', rate='10/m', method='POST'))
    def post(self, request):
        data = request.data
        email = data.get('email', '').lower()
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact = email)

            if user.is_superuser or user.is_staff:
                pass
            
            if user.role.category != "Customer":
                pass
                
            else:
                # generate otp
                user.set_otp()
                otp = user.otp

                # context = {
                #     "first_name":user.first_name,
                #     "otp":otp
                # }

                # html_content = None

                # try:
                #     html_content = render_to_string("emails/reset_password.html", context)
                # except TemplateDoesNotExist as e:
                #     print(f"Template not found: {e}")
                
                # # render html content
                # html_content = render_to_string("emails/reset_password.html", context)

                # send_email_task.delay(
                #     subject = "Reset your password",
                #     recipient_email = user.email,
                #     html_content = html_content,
                #     context = context,
                #     template_name = "emails/reset_password.html"
                # )
        except User.DoesNotExist:
            # Fail silently if email not found
            pass

        return Response({'message': 'Password reset link sent'}, status=status.HTTP_200_OK)

        


class ConfirmOtpView(APIView):
    def post(self, request):
        try:
            otp = request.data.get("otp")
            email = request.data.get('email', '').lower()

            if not otp:
                return Response({"error": "OTP is required"}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.filter(otp=otp,email=email).first()
            if not user:
                return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

            if not user.is_otp_valid():
                return Response({"error": "OTP has expired"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "OTP is valid",
                             "email":email,
                             "otp": otp}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordView(APIView):
    def post(self, request):
        try:
            data = request.data
            # print(data)
            security_question = data.get('question')
            security_answer = data.get('answer')
            # account_number = data.get('account_number')
            # card_expirey = data.get('card_expiry')
            otp = data.get('otp')
            password = data.get("password")
            email = request.data.get('email', '').lower()

            if not otp:
                raise AuthenticationFailed("OTP is required")

            user = User.objects.filter(otp=otp, email=email).first()

            if not user:
                return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)
            
            # step 1 : confirm security question and respective answer
            if security_question and security_answer:
                security_info = CustomerSecurityInformation.objects.filter(user=user).first()

                if not security_info:
                    return Response({"error": "Security information not found"}, status=status.HTTP_404_NOT_FOUND)

                if not check_password(security_answer, security_info.security_answer_hash):
                    return Response({"error": "Invalid security answer"}, status=status.HTTP_400_BAD_REQUEST)

            if not user.is_otp_valid():
                return Response({"error": "OTP has expired"}, status=status.HTTP_400_BAD_REQUEST)

            if not password:
                return Response({"error": "New password is required"}, status=status.HTTP_400_BAD_REQUEST)

            # validate password before reset
            password_error = validate_password_strength(password)
            if not password_error[0]:
                return Response({"error": password_error[1]}, status=status.HTTP_400_BAD_REQUEST)
            

            user.set_password(password)
            user.otp = None
            user.otp_expiry = None
            user.save()

            return Response({'message': 'Password has been reset successfully'}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response ({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HandleKYC(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        """
        customer can see their upploed data
        """

        user = request.user

        if user.role.role_name != "Customer":
            return Response({"error": "Access for KYC denied"}, status=status.HTTP_403_FORBIDDEN)

        
        try:
            kyc_profile = KycProfile.objects.get(user=user)
            
            kyc_documents = KycDocument.objects.filter(kyc_profile=kyc_profile)

            if not kyc_documents:
                return Response({"error": "kyc_documents not found"}, status=status.HTTP_404_NOT_FOUND)
            

            kyc_data = KycProfileSerializer(kyc_profile).data
            kyc_data['documents'] = KycDocumentSerializer(kyc_documents, many=True).data

            return Response(kyc_data, status=status.HTTP_200_OK)

        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            user = request.user

            # Ensure user is customer
            if user.role.role_name != "Customer":
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

        # validate the specific documents that are must
        
        # Add file type validation if needed
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
        file_extension = os.path.splitext(file_obj.name)[1].lower()
        if file_extension not in allowed_extensions:
            return f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        return None
    
class HandleLogoutView(APIView):
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
                    return Response({"error": "Account is inactive. Please contact Admin."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)
                
                # session logs for auditing
                session_logs = SessionLogs.objects.create(
                    user=user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    browser_agent=request.META.get('HTTP_USER_AGENT')
                )
                # update lastlogin
                update_last_login(None, user)

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
    permission_classes = [IsAuthenticated, EmployeeAccessPermission]

    def get(self,request):
        try:
            get_employees = EmployeeProfile.objects.all().order_by('-created_at')

            # filters
            role_name = request.query_params.get('role_name')
            employment_type = request.query_params.get('employment_type')
            department = request.query_params.get('department')
            search = request.query_params.get('search')

            if role_name:
                get_employees = get_employees.filter(user__role__role_name=role_name)
            if employment_type:
                get_employees = get_employees.filter(employment_type=employment_type)
            if department:
                get_employees = get_employees.filter(department__department_name=department)

            if search:
                get_employees = get_employees.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(employee_id__icontains=search) |
                    Q(user__email__icontains=search)
                )

            paginator = CustomPagination()
            paginated_employees = paginator.paginate_queryset(get_employees, request)
            serializer = EmployeeProfileSerializer(paginated_employees, many=True)
            
            return paginator.get_paginated_response(serializer.data)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):     

        data = request.data
        email = data.get("email").lower()
        password = generate_temporary_password()
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        role_name = data.get("role_name")  # e.g., "STAFF", "ADMIN"
        # department_name = data.get("department_name")  # e.g., "HR", "IT"
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
                    user.is_staff = True  # Employees are staff by default switch up later for spec
                    user.save()

                    # get department based on role name

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
                    department = Role.objects.get(role_name=role_name).department_name
                    if department:
                        dept_obj= Department.objects.get(name=department)
                        new_employee.department = dept_obj
                        new_employee.save()
                    #send the email to the employee
                    # try:
                    #     send_employee_onboarding_email.delay(new_employee.id)
                    # except Exception as e:
                    #     logger.error(f"Failed to send onboarding email to {email}: {str(e)}")

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


#tasks 1, delete/update employee 2. review kyc to allow customeer to access dashboards

class ManageEmployeeAccount(APIView):
    permission_classes = [IsAuthenticated, EmployeeAccessPermission]

    def patch(self,request,id):

        user = request.user

        print(user.id)

        data = request.data
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        role_name = data.get("role_name")



      
        try:
            employee = get_object_or_404(EmployeeProfile,id=id)

            # is user id is not in the employee
            if user.id == employee.user.id:
                return Response({"error": "You cannot modify your own account"}, status=status.HTTP_403_FORBIDDEN)

            serializer = EmployeeProfileSerializer(employee, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()

                user = employee.user
                if first_name:
                    user.first_name = first_name
                if last_name:
                    user.last_name = last_name

                if role_name:
                    role = get_object_or_404(Role, role_name=role_name)
                    if role.category == "SYSTEM":
                        return Response({"error": "Invalid role for employee"}, status=status.HTTP_400_BAD_REQUEST)
                    user.role = role
                    user.save()

                    # update the employee wit the deparrtment
                    if role.department_name:
                        employee.department = role.department_name

                        employee.save()

                user.save()

                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self,request,id):
        try:
            employee = EmployeeProfile.objects.get(id=id)
            user = employee.user
            user.is_active = False  # Soft delete by deactivating the user
            user.save()

            return Response({"message": "Employee account deactivated successfully"}, status=status.HTTP_200_OK)
        
        except EmployeeProfile.DoesNotExist:
            return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
class KYCReviewView(APIView):
    permission_classes = [IsAuthenticated, ReviewKycPermissions]

    def get(self, request):
        try:
            kyc_profiles = KycProfile.objects.select_related('user').prefetch_related('documents').order_by('-updated_at')

            # Enhanced filtering
            status_filter = request.query_params.get('status')
            user_email = request.query_params.get('user_email')
            
            if status_filter:
                kyc_profiles = kyc_profiles.filter(verification_status=status_filter)
            
            if user_email:
                kyc_profiles = kyc_profiles.filter(user__email__icontains=user_email)

            paginator = CustomPagination()
            paginated_kyc = paginator.paginate_queryset(kyc_profiles, request)
            serializer = KycProfileSerializer(paginated_kyc, many=True)
            
            return paginator.get_paginated_response(serializer.data)
        
        except Exception as e:
            logger.error(f"Error fetching KYC profiles: {str(e)}")
            return Response(
                {"error": "Unable to fetch KYC profiles"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request):
        try:
            kyc_profile_id = request.data.get('kyc_profile_id')
            new_status = request.data.get('status')
            notes = request.data.get('notes', '')

            # Validation
            if not kyc_profile_id:
                return Response(
                    {"error": "KYC profile ID is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not new_status:
                return Response(
                    {"error": "Status is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            valid_statuses = ['APPROVED', 'REJECTED', 'UNDER_REVIEW']
            if new_status not in valid_statuses:
                return Response(
                    {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            kyc_profile = get_object_or_404(KycProfile, id=kyc_profile_id)
            
            # Update KYC profile
            with transaction.atomic():     
                kyc_profile.verification_status = new_status
                kyc_profile.review_notes = notes
                kyc_profile.verified_by = request.user
                kyc_profile.verified_at = timezone.now()
                kyc_profile.save() 
                             

                # Update related documents status if needed
                if new_status in ['APPROVED', 'REJECTED']:
                    self._update_documents_status(kyc_profile, new_status, request.user)

            # Send notification
            # send_kyc_status_update.delay(kyc_profile.id, status)

            return Response(
                {"message": "KYC status updated successfully"}, 
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error updating KYC status: {str(e)}")
            return Response(
                {"error": "Unable to update KYC status"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _update_documents_status(self, kyc_profile, status, reviewed_by):
        """Update status of all documents when KYC is approved/rejected"""
        document_status_map = {
            'APPROVED': 'APPROVED',
            'REJECTED': 'REJECTED'
        }
        
        if status in document_status_map:
            kyc_profile.documents.all().update(
                status=document_status_map[status],
                reviewed_by=reviewed_by,
                reviewed_at=timezone.now()
            )