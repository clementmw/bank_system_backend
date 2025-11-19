from rest_framework.permissions import BasePermission

class CanManageEmployees(BasePermission):
    """Check role-based permission instead of Django's built-in permission system."""
    
    def has_permission(self, request, view):
        user = request.user

        # Allow superuser
        if user.is_superuser:
            return True
        
        # Ensure the user has a role
        if not user.role:
            return False
        
        # Check role permissions directly
        return user.role.permissions.filter(codename="can_manage_employees").exists()
