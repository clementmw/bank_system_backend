from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, ContentType, Group
from auth_service.models import Role, Department, User
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from decouple import config


class Command(BaseCommand):
    help = 'Setup role-based permissions and initial system data'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting system setup...")

        with transaction.atomic():
            # self.ensure_custom_permissions_exist()
            # self.create_departments()
            # self.create_roles()
            # self.assign_permissions_to_roles()
            self.create_initial_super_admin()

        self.stdout.write(self.style.SUCCESS("🎉 System setup completed successfully!"))

    # ================================================================
    # STEP 1 — ENSURE CUSTOM PERMISSIONS EXIST
    # ================================================================
    def ensure_custom_permissions_exist(self):
        """
        Ensure all custom permissions defined inside model.Meta exist in DB.
        """
        self.stdout.write("🔍 Ensuring custom permissions exist...")

        # Get all permissions from your model Meta classes
        meta_permissions = [
            # From User.Meta
            "can_manage_users", "can_view_user_profiles", "view_account_balance",
            "transfer_funds", "approve_transfer", "view_transaction_history",
            "manage_accounts", "override_limits", "view_audit_log", "process_kyc",
            "can_manage_system_settings", "can_view_system_logs",
            
            # From EmployeeProfile.Meta  
            "can_manage_employees", "can_view_employee_details",
            
            # From CustomerProfile.Meta
            "can_view_customer_accounts", "can_edit_customer_profile",
        ]

        # Get content type for User model (most permissions are attached to User)
        try:
            user_ct = ContentType.objects.get(app_label="auth_service", model="user")
        except ContentType.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ ContentType for User missing. Run migrations first."))
            return

        # Create permissions if they don't exist
        for codename in meta_permissions:
            Permission.objects.get_or_create(
                codename=codename,
                content_type=user_ct,
                defaults={"name": codename.replace("_", " ").title()}
            )

        self.stdout.write(self.style.SUCCESS("✓ Custom permissions verified."))

    # ================================================================
    # STEP 2 — DEPARTMENTS
    # ================================================================
    def create_departments(self):
        self.stdout.write("🏢 Creating departments...")

        departments = [
            ('FINANCE', 'FIN'),
            ('OPERATIONS', 'OPS'), 
            ('IT', 'IT'),
            ('HR', 'HR'),
            ('RISK', 'RISK'),
            ('CUSTOMER_SERVICE', 'CS'),
        ]

        self.created_departments = {}
        
        for name, code in departments:
            dept, created = Department.objects.get_or_create(
                name=name, 
                defaults={'code': code}
            )
            self.created_departments[name] = dept

        self.stdout.write(self.style.SUCCESS("✓ Departments ready."))

    # ================================================================
    # STEP 3 — ROLES (Updated with department assignment)
    # ================================================================
    def create_roles(self):
        self.stdout.write("👥 Creating roles...")

        # Map roles to departments
        roles_data = [
            # SYSTEM ROLES
            ('SUPER_ADMIN', 'Super Administrator', 'SYSTEM', None, True),
            ('ADMIN', 'Administrator', 'SYSTEM', None, True),
            
            # FINANCE DEPARTMENT ROLES
            ('FINANCE_MANAGER', 'Finance Manager', 'BUSINESS', 'FINANCE', False),
            ('FINANCE_OFFICER', 'Finance Officer', 'BUSINESS', 'FINANCE', False),
            
            # OPERATIONS DEPARTMENT ROLES  
            ('OPERATIONS_MANAGER', 'Operations Manager', 'BUSINESS', 'OPERATIONS', False),
            ('OPERATIONS_STAFF', 'Operations Staff', 'BUSINESS', 'OPERATIONS', False),
            
            # IT DEPARTMENT ROLES
            ('IT_MANAGER', 'IT Manager', 'SYSTEM', 'IT', False),
            ('IT_STAFF', 'IT Staff', 'SYSTEM', 'IT', False),
            
            # HR DEPARTMENT ROLES
            ('HR_MANAGER', 'HR Manager', 'SUPPORT', 'HR', False),
            ('HR_STAFF', 'HR Staff', 'SUPPORT', 'HR', False),
            
            # CUSTOMER SERVICE DEPARTMENT ROLES
            ('CUSTOMER_SERVICE_MANAGER', 'Customer Service Manager', 'SUPPORT', 'CUSTOMER_SERVICE', False),
            ('CUSTOMER_SERVICE_STAFF', 'Customer Service Staff', 'SUPPORT', 'CUSTOMER_SERVICE', False),
            
            # RISK DEPARTMENT ROLES
            ('RISK_MANAGER', 'Risk Manager', 'BUSINESS', 'RISK', False),
            ('RISK_STAFF', 'Risk Staff', 'BUSINESS', 'RISK', False),
            
            # CUSTOMER ROLE (No department)
            ('CUSTOMER', 'Customer', 'BUSINESS', None, False),
        ]

        self.roles = {}

        for name, display, category, dept_name, system_role in roles_data:
            department = self.created_departments.get(dept_name) if dept_name else None
            
            role, created = Role.objects.get_or_create(
                name=name,
                defaults={
                    "display_name": display,
                    "category": category,
                    "department_name": department,
                    "is_system_role": system_role
                }
            )

            self.roles[name] = role

        self.stdout.write(self.style.SUCCESS("✓ Roles created."))

    # ================================================================
    # STEP 4 — ASSIGN PERMISSIONS TO ROLES (Simplified - no groups)
    # ================================================================
    def assign_permissions_to_roles(self):
        self.stdout.write("🔑 Assigning permissions to roles...")

        # Define permissions for each role directly
        role_permissions = {
            'SUPER_ADMIN': [
                # All permissions
            ],
            
            'ADMIN': [
                'can_manage_users', 'can_view_user_profiles', 'can_manage_employees',
                'can_view_employee_details', 'view_account_balance', 'transfer_funds',
                'approve_transfer', 'view_transaction_history', 'manage_accounts',
                'override_limits', 'view_audit_log', 'process_kyc', 'can_manage_system_settings',
                'can_view_system_logs', 'can_view_customer_accounts', 'can_edit_customer_profile'
            ],
            
            'FINANCE_MANAGER': [
                'view_account_balance', 'transfer_funds', 'approve_transfer', 
                'view_transaction_history', 'manage_accounts', 'override_limits',
                'view_audit_log', 'can_view_customer_accounts'
            ],
            
            'FINANCE_OFFICER': [
                'view_account_balance', 'transfer_funds', 'view_transaction_history',
                'can_view_customer_accounts'
            ],
            
            'OPERATIONS_MANAGER': [
                'view_account_balance', 'transfer_funds', 'view_transaction_history',
                'manage_accounts', 'can_view_customer_accounts'
            ],
            
            'OPERATIONS_STAFF': [
                'view_account_balance', 'view_transaction_history', 'can_view_customer_accounts'
            ],
            
            'IT_MANAGER': [
                'can_manage_system_settings', 'can_view_system_logs', 'view_audit_log',
                'can_manage_users', 'can_view_user_profiles'
            ],
            
            'IT_STAFF': [
                'can_view_system_logs', 'view_audit_log', 'can_view_user_profiles'
            ],
            
            'HR_MANAGER': [
                'can_manage_employees', 'can_view_employee_details', 'can_manage_users',
                'can_view_user_profiles'
            ],
            
            'HR_STAFF': [
                'can_view_employee_details', 'can_view_user_profiles'
            ],
            
            'CUSTOMER_SERVICE_MANAGER': [
                'can_view_customer_accounts', 'can_edit_customer_profile', 
                'view_transaction_history', 'process_kyc'
            ],
            
            'CUSTOMER_SERVICE_STAFF': [
                'can_view_customer_accounts', 'view_transaction_history', 'process_kyc'
            ],
            
            'RISK_MANAGER': [
                'process_kyc', 'view_audit_log', 'view_account_balance', 
                'view_transaction_history', 'can_view_customer_accounts'
            ],
            
            'RISK_STAFF': [
                'process_kyc', 'view_audit_log', 'view_transaction_history'
            ],
            
            'CUSTOMER': [
                'view_account_balance', 'transfer_funds', 'view_transaction_history'
            ]
        }

        # Assign permissions to each role
        for role_name, permission_codenames in role_permissions.items():
            role = self.roles[role_name]
            
            if role_name == "SUPER_ADMIN":
                # Super admin gets all permissions
                all_permissions = Permission.objects.all()
                role.permissions.set(all_permissions)
            else:
                # Get specific permissions for the role
                permissions = Permission.objects.filter(codename__in=permission_codenames)
                role.permissions.set(permissions)
                
            self.stdout.write(f"  ✓ {role.display_name}: {role.permissions.count()} permissions")

        self.stdout.write(self.style.SUCCESS("✓ Permissions assigned to roles."))

    # ================================================================
    # STEP 5 — INITIAL SUPER ADMIN
    # ================================================================
    def create_initial_super_admin(self):
        self.stdout.write("🛡 Creating initial SUPER ADMIN...")

        try:
            role = Role.objects.get(name="SUPER_ADMIN")

            admin, created = User.objects.get_or_create(
                email=config("ADMIN_EMAIL", default="admin@example.com"),
                defaults={
                    "first_name": "System",
                    "last_name": "Administrator", 
                    "is_superuser": True,
                    "is_staff": True,
                    "role": role,
                    "is_active": True
                }
            )

            if created:
                admin.set_password(config("ADMIN_PASSWORD", default="admin123"))
                admin.save()
                self.stdout.write(self.style.SUCCESS("✓ Super admin created successfully."))
            else:
                self.stdout.write(self.style.WARNING("⚠ Super admin already exists."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Super admin creation failed: {str(e)}"))