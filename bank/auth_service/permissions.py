from rest_framework.permissions import BasePermission

class HasRolePermission(BasePermission): #for global routes
    """
    Check for multiple role-based permissions.
    Usage: permission_classes = [HasRolePermission('can_view_employees', 'can_manage_employees')]
    """
    
    def __init__(self, *permissions):
        self.permissions = permissions
    
    def has_permission(self, request, view):
        user = request.user

        # Allow superuser
        if user.is_superuser:
            return True
        
        # Ensure the user has a role
        if not user.role:
            return False
        
        # Check if user has ANY of the specified permissions
        return user.role.permissions.filter(
            codename__in=self.permissions
        ).exists()


class EmployeeAccessPermission(BasePermission):
    """
    Different permissions for different HTTP methods:
    - GET: requires can_view_employees
    - POST/PUT/PATCH/DELETE: requires can_manage_employees
    """
    
    def has_permission(self, request, view):
        user = request.user

        # Allow superuser
        if user.is_superuser:
            return True
        
        # Ensure the user has a role
        if not user.role:
            return False
        
        # GET method - only view permission required
        if request.method in ['GET','PUT', 'PATCH']:
            return user.role.permissions.filter(
                codename='can_view_employee_details'
            ).exists()
        
        # POST, PUT, PATCH, DELETE methods - manage permission required
        elif request.method in ['POST', 'DELETE']:
            return user.role.permissions.filter(
                codename='can_manage_employees'
            ).exists()
        
        # For any other methods, deny by default
        return False

class ReviewKycPermissions(BasePermission):
    required_permissions = ['can_view_user_profiles']
    def has_permission(self, request, view):

        user = request.user

        # Allow superuser
        if user.is_superuser:
            return True

        # Ensure the user has a role
        if not user.role:
            return False

        # Check if user has the required permission
        return user.role.permissions.filter(
            codename__in=self.required_permissions
        ).exists()
