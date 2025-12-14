import json
import logging
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from io import BytesIO
from django.core.handlers.wsgi import WSGIRequest
import copy
from .models import AuditLog

logger = logging.getLogger(__name__)

class SimpleAuditMiddleware(MiddlewareMixin):
    """
    Enhanced audit middleware with request body preservation
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def __call__(self, request):
        # Store original request body for audit logging
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Read and store the request body
            request._body = request.body
            # Create a copy for potential re-reading
            if hasattr(request, '_body'):
                request._original_body = request._body
        
        response = self.get_response(request)
        
        # Log if authenticated and modifying data
        if (request.user and request.user.is_authenticated and  request.user.is_staff and
            request.method in ['POST', 'PUT', 'PATCH', 'DELETE'] and
            200 <= response.status_code < 400):
            
            try:
                self.create_audit_log(request, response)
            except Exception as e:
                logger.error(f"Audit logging failed: {str(e)}", exc_info=True)
        
        return response
    
    def create_audit_log(self, request, response):
        """Create audit log entry"""
        try:
            # Get request data - try multiple approaches
            request_data = self.get_request_data(request)
            
            # Create audit log
            audit_log = AuditLog(
                user=request.user,
                action=request.method,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                metadata=request_data,
            )
            
            # Try to extract resource info from response data if available
            try:
                if hasattr(response, 'data'):
                    response_data = response.data
                    # Extract resource info - adjust based on your response structure
                    if isinstance(response_data, dict):
                        if 'account_number' in response_data:
                            audit_log.resource_type = 'Account'
                            audit_log.resource_id = response_data.get('account_number')
                        elif 'id' in response_data:
                            audit_log.resource_id = response_data.get('id')
            except:
                pass
            
            audit_log.save()
            logger.info(f"Audit log created for {request.user}: {request.method} {request.path}")
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}", exc_info=True)
    
    def get_request_data(self, request):
        """Safely get request data"""
        request_data = {}
        
        # Method 1: Try to get from stored body
        try:
            if hasattr(request, '_original_body') and request._original_body:
                body = request._original_body
                if body:
                    request_data = json.loads(body.decode('utf-8'))
                return request_data
        except:
            pass
        
        # Method 2: Try request.POST for form data
        try:
            if request.POST:
                request_data = dict(request.POST)
                # Flatten lists
                for key, value in request_data.items():
                    if isinstance(value, list) and len(value) == 1:
                        request_data[key] = value[0]
                return request_data
        except:
            pass
        
        # Method 3: Try request.data if it's a DRF request
        try:
            if hasattr(request, 'data'):
                return dict(request.data)
        except:
            pass
        
        # Method 4: Get raw body as string
        try:
            if hasattr(request, '_body') and request._body:
                raw_body = request._body.decode('utf-8', errors='ignore')[:1000]
                return {'raw_body': raw_body}
        except:
            pass
        
        return request_data
    
    def get_client_ip(self, request):
        """Get client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', 'unknown')