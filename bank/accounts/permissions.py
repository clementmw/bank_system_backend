from rest_framework.permissions import BasePermission


class HasAccountPermission(BasePermission): 
    """
    diffrent permissions for different HTTP methods:
    - GET: requires can_view_all_accounts
    - POST/PUT/PATCH/DELETE: requires can_manage_accounts,can_modify_account_limits,can_freeze_accounts
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
        if request.method in ['GET']:
            return user.role.permissions.filter(
                codename='can_view_all_accounts'
            ).exists()

        # POST, PUT, PATCH, DELETE methods - manage permission required
        elif request.method in ['POST', 'DELETE', 'PUT']:
            return user.role.permissions.filter(
                codename__in=['can_modify_account_limits', 'can_freeze_accounts','can_close_account']
            ).exists()

        # For any other methods, deny by default
        return False


