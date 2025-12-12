from django.test import TestCase

"""
Comprehensive unit tests for the authentication app
Run with: python manage.py test authentication.tests
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from datetime import timedelta
from decimal import Decimal
import secrets

from .models import *


User = get_user_model()


class DepartmentModelTest(TestCase):
    """Test suite for Department model"""
    
    def setUp(self):
        self.department_data = {
            'name': 'FINANCE',
            'code': 'FIN01'
        }
    
    def test_create_department(self):
        """Test basic department creation"""
        department = Department.objects.create(**self.department_data)
        self.assertEqual(department.name, 'FINANCE')
        self.assertEqual(department.code, 'FIN01')
        self.assertTrue(department.is_active)
        self.assertIsNotNone(department.id)
        self.assertIsNotNone(department.created_at)
    
    def test_department_unique_name(self):
        """Test that department name must be unique"""
        Department.objects.create(**self.department_data)
        with self.assertRaises(IntegrityError):
            Department.objects.create(**self.department_data)
    
    def test_department_unique_code(self):
        """Test that department code must be unique"""
        Department.objects.create(**self.department_data)
        with self.assertRaises(IntegrityError):
            Department.objects.create(name='IT', code='FIN01')
    
    def test_department_str_representation(self):
        """Test string representation of department"""
        department = Department.objects.create(**self.department_data)
        self.assertEqual(str(department), 'FINANCE')
    
    def test_department_hod_assignment(self):
        """Test assigning Head of Department"""
        role = Role.objects.create(
            role_name='Manager',
            category='STAFF'
        )
        user = User.objects.create_user(
            email='hod@test.com',
            password='testpass123',
            role=role
        )
        department = Department.objects.create(
            name='FINANCE',
            code='FIN01',
            hod=user
        )
        self.assertEqual(department.hod, user)
        self.assertEqual(user.hod_of_department.first(), department)


class RoleModelTest(TestCase):
    """Test suite for Role model"""
    
    def setUp(self):
        self.department = Department.objects.create(
            name='FINANCE',
            code='FIN01'
        )
        self.role_data = {
            'role_name': 'Account Manager',
            'category': 'STAFF',
            'department_name': self.department,
            'description': 'Manages customer accounts'
        }
    
    def test_create_role(self):
        """Test basic role creation"""
        role = Role.objects.create(**self.role_data)
        self.assertEqual(role.role_name, 'Account Manager')
        self.assertEqual(role.category, 'STAFF')
        self.assertFalse(role.is_system_role)
        self.assertTrue(role.is_active)
    
    def test_role_str_representation(self):
        """Test string representation of role"""
        role = Role.objects.create(**self.role_data)
        self.assertEqual(str(role), 'Account Manager')
    
    def test_system_role_flag(self):
        """Test system role flag"""
        role = Role.objects.create(
            role_name='Super Admin',
            category='SYSTEM',
            is_system_role=True
        )
        self.assertTrue(role.is_system_role)
    
    def test_role_without_department(self):
        """Test creating role without department"""
        role = Role.objects.create(
            role_name='Customer',
            category='Customer'
        )
        self.assertIsNone(role.department_name)


class UserModelTest(TestCase):
    """Test suite for User model"""
    
    def setUp(self):
        self.role = Role.objects.create(
            role_name='Customer',
            category='Customer'
        )
        self.user_data = {
            'email': 'testuser@example.com',
            'password': 'SecurePass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'role': self.role
        }
    
    def test_create_user(self):
        """Test user creation with create_user method"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertTrue(user.check_password('SecurePass123!'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
    
    def test_create_superuser(self):
        """Test superuser creation"""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!',
            role=self.role
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
    
    def test_user_email_uniqueness(self):
        """Test that email must be unique"""
        User.objects.create_user(**self.user_data)
        with self.assertRaises(IntegrityError):
            User.objects.create_user(**self.user_data)
    
    def test_user_email_normalization(self):
        """Test that email is normalized"""
        user = User.objects.create_user(
            email='Test.User@EXAMPLE.COM',
            password='testpass123',
            role=self.role
        )
        self.assertEqual(user.email, 'Test.User@example.com')
    
    def test_user_without_email_raises_error(self):
        """Test that creating user without email raises error"""
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='test', role=self.role)
    
    def test_user_str_representation(self):
        """Test string representation of user"""
        user = User.objects.create_user(**self.user_data)
        expected = f"John - Customer - Doe - testuser@example.com"
        self.assertEqual(str(user), expected)
    
    def test_set_otp(self):
        """Test OTP generation"""
        user = User.objects.create_user(**self.user_data)
        user.set_otp()
        self.assertIsNotNone(user.otp)
        self.assertEqual(len(user.otp), 6)
        self.assertIsNotNone(user.otp_expiry)
    
    def test_is_otp_valid_within_time(self):
        """Test OTP validation within valid time"""
        user = User.objects.create_user(**self.user_data)
        user.set_otp()
        self.assertTrue(user.is_otp_valid())
    
    def test_is_otp_valid_expired(self):
        """Test OTP validation when expired"""
        user = User.objects.create_user(**self.user_data)
        user.otp = '123456'
        user.otp_expiry = timezone.now() - timedelta(minutes=5)
        user.save()
        self.assertFalse(user.is_otp_valid())
    
    def test_is_otp_valid_no_expiry(self):
        """Test OTP validation when no expiry set"""
        user = User.objects.create_user(**self.user_data)
        self.assertFalse(user.is_otp_valid())
    
    def test_generate_email_token(self):
        """Test email verification token generation"""
        user = User.objects.create_user(**self.user_data)
        token = user.generate_email_token()
        self.assertIsNotNone(token)
        self.assertEqual(len(token), 64)
        self.assertEqual(user.email_verification_token, token)
        self.assertIsNotNone(user.email_verification_expiry)
    
    def test_verify_email_with_valid_token(self):
        """Test email verification with valid token"""
        user = User.objects.create_user(**self.user_data)
        user.is_active = False
        user.save()
        token = user.generate_email_token()
        
        result = user.verify_email(token)
        self.assertTrue(result)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.email_verification_token)
        self.assertIsNone(user.email_verification_expiry)
    
    def test_verify_email_with_invalid_token(self):
        """Test email verification with invalid token"""
        user = User.objects.create_user(**self.user_data)
        user.generate_email_token()
        
        result = user.verify_email('invalid_token')
        self.assertFalse(result)
    
    def test_verify_email_with_expired_token(self):
        """Test email verification with expired token"""
        user = User.objects.create_user(**self.user_data)
        token = user.generate_email_token()
        user.email_verification_expiry = timezone.now() - timedelta(hours=25)
        user.save()
        
        result = user.verify_email(token)
        self.assertFalse(result)


class EmployeeProfileModelTest(TestCase):
    """Test suite for EmployeeProfile model"""
    
    def setUp(self):
        self.department = Department.objects.create(
            name='IT',
            code='IT01'
        )
        self.role = Role.objects.create(
            role_name='Developer',
            category='STAFF',
            department_name=self.department
        )
        self.user = User.objects.create_user(
            email='employee@test.com',
            password='testpass123',
            role=self.role,
            first_name='Jane',
            last_name='Smith'
        )
        self.employee_data = {
            'user': self.user,
            'employee_id': 'EMP001',
            'department': self.department,
            'employment_type': 'FULL_TIME',
            'job_title': 'Senior Developer',
            'phone_number': '+254712345678'
        }
    
    def test_create_employee_profile(self):
        """Test employee profile creation"""
        employee = EmployeeProfile.objects.create(**self.employee_data)
        self.assertEqual(employee.employee_id, 'EMP001')
        self.assertEqual(employee.employment_type, 'FULL_TIME')
        self.assertTrue(employee.is_active_employee)
        self.assertTrue(employee.is_active)
    
    def test_employee_unique_employee_id(self):
        """Test that employee_id must be unique"""
        EmployeeProfile.objects.create(**self.employee_data)
        
        another_user = User.objects.create_user(
            email='another@test.com',
            password='test123',
            role=self.role
        )
        with self.assertRaises(IntegrityError):
            EmployeeProfile.objects.create(
                user=another_user,
                employee_id='EMP001',
                phone_number='+254712345679'
            )
    
    def test_employee_unique_phone_number(self):
        """Test that phone number must be unique"""
        EmployeeProfile.objects.create(**self.employee_data)
        
        another_user = User.objects.create_user(
            email='another@test.com',
            password='test123',
            role=self.role
        )
        with self.assertRaises(IntegrityError):
            EmployeeProfile.objects.create(
                user=another_user,
                employee_id='EMP002',
                phone_number='+254712345678'
            )
    
    def test_employee_one_to_one_with_user(self):
        """Test one-to-one relationship with User"""
        employee = EmployeeProfile.objects.create(**self.employee_data)
        self.assertEqual(self.user.employee_profile, employee)
    
    def test_employee_str_representation(self):
        """Test string representation of employee"""
        employee = EmployeeProfile.objects.create(**self.employee_data)
        expected = f"EMP001 - employee@test.com (Senior Developer)"
        self.assertEqual(str(employee), expected)
    
    def test_employee_with_emergency_contact(self):
        """Test employee with emergency contact info"""
        self.employee_data['emergency_contact_name'] = 'John Doe'
        self.employee_data['emergency_contact_phone'] = '+254722222222'
        employee = EmployeeProfile.objects.create(**self.employee_data)
        self.assertEqual(employee.emergency_contact_name, 'John Doe')


class CustomerProfileModelTest(TestCase):
    """Test suite for CustomerProfile model"""
    
    def setUp(self):
        self.role = Role.objects.create(
            role_name='Customer',
            category='Customer'
        )
        self.user = User.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            role=self.role,
            first_name='Alice',
            last_name='Johnson'
        )
        self.customer_data = {
            'user': self.user,
            'customer_id': 'CUST001',
            'phone_number': '+254712345678',
            'customer_tier': 'STANDARD'
        }
    
    def test_create_customer_profile(self):
        """Test customer profile creation"""
        customer = CustomerProfile.objects.create(**self.customer_data)
        self.assertEqual(customer.customer_id, 'CUST001')
        self.assertEqual(customer.customer_tier, 'STANDARD')
        self.assertEqual(customer.risk_rating, 'LOW')
        self.assertTrue(customer.is_active)
    
    def test_customer_unique_customer_id(self):
        """Test that customer_id must be unique"""
        CustomerProfile.objects.create(**self.customer_data)
        
        another_user = User.objects.create_user(
            email='another@test.com',
            password='test123',
            role=self.role
        )
        with self.assertRaises(IntegrityError):
            CustomerProfile.objects.create(
                user=another_user,
                customer_id='CUST001',
                phone_number='+254712345679'
            )
    
    def test_customer_unique_phone_number(self):
        """Test that phone number must be unique"""
        CustomerProfile.objects.create(**self.customer_data)
        
        another_user = User.objects.create_user(
            email='another@test.com',
            password='test123',
            role=self.role
        )
        with self.assertRaises(IntegrityError):
            CustomerProfile.objects.create(
                user=another_user,
                customer_id='CUST002',
                phone_number='+254712345678'
            )
    
    def test_customer_str_representation(self):
        """Test string representation of customer"""
        customer = CustomerProfile.objects.create(**self.customer_data)
        expected = "Customer CUST001 - customer@test.com"
        self.assertEqual(str(customer), expected)
    
    def test_customer_tier_choices(self):
        """Test different customer tiers"""
        tiers = ['STANDARD', 'PREMIUM', 'BUSINESS']
        for tier in tiers:
            self.customer_data['customer_id'] = f'CUST_{tier}'
            self.customer_data['phone_number'] = f'+25471234{tiers.index(tier)}'
            self.customer_data['customer_tier'] = tier
            
            new_user = User.objects.create_user(
                email=f'{tier.lower()}@test.com',
                password='test123',
                role=self.role
            )
            self.customer_data['user'] = new_user
            
            customer = CustomerProfile.objects.create(**self.customer_data)
            self.assertEqual(customer.customer_tier, tier)
    
    def test_customer_marketing_preferences(self):
        """Test marketing preferences flag"""
        customer = CustomerProfile.objects.create(**self.customer_data)
        self.assertFalse(customer.marketing_preferences)
        
        customer.marketing_preferences = True
        customer.save()
        self.assertTrue(customer.marketing_preferences)


class KycProfileModelTest(TestCase):
    """Test suite for KycProfile model"""
    
    def setUp(self):
        self.role = Role.objects.create(
            role_name='Customer',
            category='Customer'
        )
        self.user = User.objects.create_user(
            email='kyc_user@test.com',
            password='testpass123',
            role=self.role
        )
        self.verifier_role = Role.objects.create(
            role_name='KYC Officer',
            category='STAFF'
        )
        self.verifier = User.objects.create_user(
            email='verifier@test.com',
            password='testpass123',
            role=self.verifier_role
        )
    
    def test_create_kyc_profile(self):
        """Test KYC profile creation"""
        kyc = KycProfile.objects.create(user=self.user)
        self.assertEqual(kyc.verification_status, 'INCOMPLETE')
        self.assertIsNone(kyc.verified_at)
        self.assertIsNone(kyc.verified_by)
    
    def test_kyc_str_representation(self):
        """Test string representation of KYC profile"""
        kyc = KycProfile.objects.create(user=self.user)
        expected = f"KYC Profile - kyc_user@test.com - INCOMPLETE"
        self.assertEqual(str(kyc), expected)
    
    def test_kyc_verification_workflow(self):
        """Test KYC verification workflow"""
        kyc = KycProfile.objects.create(user=self.user)
        
        # Move to pending
        kyc.verification_status = 'PENDING'
        kyc.save()
        self.assertEqual(kyc.verification_status, 'PENDING')
        
        # Verify
        kyc.verification_status = 'VERIFIED'
        kyc.verified_by = self.verifier
        kyc.verified_at = timezone.now()
        kyc.review_notes = 'All documents verified'
        kyc.save()
        
        self.assertEqual(kyc.verification_status, 'VERIFIED')
        self.assertIsNotNone(kyc.verified_at)
        self.assertEqual(kyc.verified_by, self.verifier)
    
    def test_kyc_rejection(self):
        """Test KYC rejection"""
        kyc = KycProfile.objects.create(
            user=self.user,
            verification_status='PENDING'
        )
        
        kyc.verification_status = 'REJECTED'
        kyc.review_notes = 'Documents expired'
        kyc.verified_by = self.verifier
        kyc.save()
        
        self.assertEqual(kyc.verification_status, 'REJECTED')
        self.assertIn('expired', kyc.review_notes)


class KycDocumentModelTest(TestCase):
    """Test suite for KycDocument model"""
    
    def setUp(self):
        self.role = Role.objects.create(
            role_name='Customer',
            category='Customer'
        )
        self.user = User.objects.create_user(
            email='doc_user@test.com',
            password='testpass123',
            role=self.role
        )
        self.kyc_profile = KycProfile.objects.create(user=self.user)
    
    def test_create_kyc_document(self):
        """Test KYC document creation"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file = SimpleUploadedFile(
            "national_id.pdf",
            b"file_content",
            content_type="application/pdf"
        )
        
        doc = KycDocument.objects.create(
            kyc_profile=self.kyc_profile,
            document_type='NATIONAL_ID',
            document_upload=file
        )
        
        self.assertEqual(doc.status, 'PENDING')
        self.assertIsNotNone(doc.file_name)
        self.assertIsNotNone(doc.file_size)
    
    def test_kyc_document_str_representation(self):
        """Test string representation of KYC document"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file = SimpleUploadedFile("id.pdf", b"content")
        doc = KycDocument.objects.create(
            kyc_profile=self.kyc_profile,
            document_type='PASSPORT',
            document_upload=file
        )
        
        expected = f"doc_user@test.com - PASSPORT - PENDING"
        self.assertEqual(str(doc), expected)
    
    def test_kyc_document_unique_constraint(self):
        """Test that one document type per KYC profile"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file1 = SimpleUploadedFile("id1.pdf", b"content1")
        KycDocument.objects.create(
            kyc_profile=self.kyc_profile,
            document_type='NATIONAL_ID',
            document_upload=file1
        )
        
        file2 = SimpleUploadedFile("id2.pdf", b"content2")
        with self.assertRaises(IntegrityError):
            KycDocument.objects.create(
                kyc_profile=self.kyc_profile,
                document_type='NATIONAL_ID',
                document_upload=file2
            )
    
    def test_kyc_document_expiry(self):
        """Test document with expiry date"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from datetime import date
        
        file = SimpleUploadedFile("passport.pdf", b"content")
        expiry = date.today() + timedelta(days=365)
        
        doc = KycDocument.objects.create(
            kyc_profile=self.kyc_profile,
            document_type='PASSPORT',
            document_upload=file,
            expiry_date=expiry
        )
        
        self.assertEqual(doc.expiry_date, expiry)


class SessionLogsModelTest(TestCase):
    """Test suite for SessionLogs model"""
    
    def setUp(self):
        self.role = Role.objects.create(
            role_name='Customer',
            category='Customer'
        )
        self.user = User.objects.create_user(
            email='session_user@test.com',
            password='testpass123',
            role=self.role
        )
    
    def test_create_session_log(self):
        """Test session log creation"""
        session = SessionLogs.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            browser_agent='Mozilla/5.0'
        )
        
        self.assertIsNotNone(session.login_time)
        self.assertIsNone(session.logout_time)
        self.assertEqual(session.ip_address, '192.168.1.1')
    
    def test_session_str_representation(self):
        """Test string representation of session log"""
        session = SessionLogs.objects.create(user=self.user)
        self.assertIn('session_user@test.com', str(session))
    
    def test_session_logout(self):
        """Test recording logout time"""
        session = SessionLogs.objects.create(user=self.user)
        self.assertIsNone(session.logout_time)
        
        session.logout_time = timezone.now()
        session.save()
        self.assertIsNotNone(session.logout_time)
    
    def test_multiple_sessions_per_user(self):
        """Test that user can have multiple session logs"""
        SessionLogs.objects.create(user=self.user, ip_address='192.168.1.1')
        SessionLogs.objects.create(user=self.user, ip_address='192.168.1.2')
        
        self.assertEqual(self.user.session_logs.count(), 2)


class BaseModelTest(TestCase):
    """Test suite for BaseModel functionality"""
    
    def test_base_model_fields(self):
        """Test that all models inherit BaseModel fields"""
        role = Role.objects.create(
            role_name='Test Role',
            category='STAFF'
        )
        
        # Check UUID
        self.assertIsNotNone(role.id)
        
        # Check timestamps
        self.assertIsNotNone(role.created_at)
        self.assertIsNotNone(role.updated_at)
        
        # Check is_active
        self.assertTrue(role.is_active)
    
    def test_updated_at_changes_on_save(self):
        """Test that updated_at changes when model is saved"""
        role = Role.objects.create(
            role_name='Test Role',
            category='STAFF'
        )
        original_updated = role.updated_at
        
        # Wait a bit and update
        import time
        time.sleep(0.1)
        
        role.description = 'Updated description'
        role.save()
        
        self.assertGreater(role.updated_at, original_updated)
    
    def test_soft_delete_via_is_active(self):
        """Test soft delete using is_active flag"""
        department = Department.objects.create(
            name='FINANCE',
            code='FIN01'
        )
        
        department.is_active = False
        department.save()
        
        # Still exists in database
        self.assertTrue(
            Department.objects.filter(id=department.id).exists()
        )
        
        # But marked as inactive
        self.assertFalse(department.is_active)


class UserPermissionsTest(TestCase):
    """Test suite for User model permissions"""
    
    def setUp(self):
        self.role = Role.objects.create(
            role_name='Test Role',
            category='STAFF'
        )
        self.user = User.objects.create_user(
            email='perm_user@test.com',
            password='testpass123',
            role=self.role
        )
    
    def test_user_custom_permissions_exist(self):
        """Test that custom permissions are created"""
        from django.contrib.auth.models import Permission
        
        permission_codenames = [
            'can_manage_users',
            'view_account_balance',
            'transfer_funds',
            'approve_transfer'
        ]
        
        for codename in permission_codenames:
            self.assertTrue(
                Permission.objects.filter(codename=codename).exists(),
                f"Permission {codename} does not exist"
            )
    
    def test_assign_permission_to_user(self):
        """Test assigning permission to user"""
        from django.contrib.auth.models import Permission
        
        perm = Permission.objects.get(codename='view_account_balance')
        self.user.user_permissions.add(perm)
        
        self.assertTrue(
            self.user.has_perm('authentication.view_account_balance')
        )


class IntegrationTest(TransactionTestCase):
    """Integration tests for related models"""
    
    def test_complete_customer_onboarding_flow(self):
        """Test complete customer onboarding workflow"""
        # Create role
        role = Role.objects.create(
            role_name='Customer',
            category='Customer'
        )
        
        # Create user
        user = User.objects.create_user(
            email='onboarding@test.com',
            password='SecurePass123!',
            first_name='Test',
            last_name='User',
            role=role
        )
        user.is_active = False
        user.save()
        
        # Generate email verification token
        token = user.generate_email_token()
        self.assertIsNotNone(token)
        
        # Verify email
        verified = user.verify_email(token)
        self.assertTrue(verified)
        self.assertTrue(user.is_active)
        
        # Create customer profile
        customer = CustomerProfile.objects.create(
            user=user,
            customer_id='CUST_INT_001',
            phone_number='+254700000000',
            customer_tier='STANDARD'
        )
        
        # Create KYC profile
        kyc = KycProfile.objects.create(user=user)
        self.assertEqual(kyc.verification_status, 'INCOMPLETE')
        
        # Create session log
        session = SessionLogs.objects.create(
            user=user,
            ip_address='192.168.1.100'
        )
        
        # Verify all relationships
        self.assertEqual(user.customer_profile, customer)
        self.assertEqual(user.kyc_profile, kyc)
        self.assertIn(session, user.session_logs.all())
    
    def test_employee_with_department_and_role(self):
        """Test employee creation with department and role"""
        # Create department
        department = Department.objects.create(
            name='IT',
            code='IT01'
        )
        
        # Create role
        role = Role.objects.create(
            role_name='Developer',
            category='STAFF',
            department_name=department
        )
        
        # Create user
        user = User.objects.create_user(
            email='employee_int@test.com',
            password='testpass123',
            role=role
        )
        
        # Create employee profile
        employee = EmployeeProfile.objects.create(
            user=user,
            employee_id='EMP_INT_001',
            department=department,
            job_title='Senior Developer',
            phone_number='+254711111111'
        )
        
        # Verify relationships
        self.assertEqual(employee.department, department)
        self.assertEqual(user.role.department_name, department)
        self.assertIn(employee, department.employees.all())