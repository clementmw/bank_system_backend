import uuid
import json
import hashlib
from datetime import datetime
import base64
import json
from django.utils import timezone
from django.db.models import Q


# def generate_idempotency_key(user_id, account_no, amount):
#     """
#     Generate a unique idempotency key based on user, transaction, amount
#     """
#     key_components = f"{user_id}:{account_no}:{amount}:{datetime.now().isoformat()}"
#     return hashlib.sha256(key_components.encode()).hexdigest()


def generate_transaction_ref():
    """
    Generate a unique transaction reference
    """
    return str(uuid.uuid4()).replace('-', '').upper()[:10]

class CursorPagination:
    """
    Custom cursor-based pagination for efficient transaction batching
    Uses created_at timestamp for cursor positioning
    """
    
    def __init__(self, page_size=50, max_page_size=200):
        self.page_size = page_size
        self.max_page_size = max_page_size
    
    def encode_cursor(self, created_at, transaction_id):
        """Encode cursor from timestamp and ID"""
        cursor_data = {
            'created_at': created_at.isoformat(),
            'id': str(transaction_id)
        }
        cursor_json = json.dumps(cursor_data)
        return base64.b64encode(cursor_json.encode()).decode()
    
    def decode_cursor(self, cursor_string):
        """Decode cursor to timestamp and ID"""
        try:
            cursor_json = base64.b64decode(cursor_string.encode()).decode()
            cursor_data = json.loads(cursor_json)
            return {
                'created_at': datetime.fromisoformat(cursor_data['created_at']),
                'id': cursor_data['id']
            }
        except (ValueError, KeyError, json.JSONDecodeError):
            return None
    
    def paginate_queryset(self, queryset, request):
        """
        Paginate queryset using cursor
        Returns: (results, next_cursor, previous_cursor, has_more)
        """
        # Get page size from request (with limits)
        page_size = int(request.GET.get('page_size', self.page_size))
        page_size = min(page_size, self.max_page_size)
        
        # Get cursor from request
        cursor = request.GET.get('cursor')
        direction = request.GET.get('direction', 'next')  # 'next' or 'previous'
        
        if cursor:
            cursor_data = self.decode_cursor(cursor)
            if not cursor_data:
                # Invalid cursor, return first page
                cursor_data = None
        else:
            cursor_data = None
        
        # Build query based on cursor
        if cursor_data:
            cursor_time = cursor_data['created_at']
            cursor_id = cursor_data['id']
            
            if direction == 'next':
                # Get records older than cursor
                queryset = queryset.filter(
                    Q(created_at__lt=cursor_time) |
                    Q(created_at=cursor_time, id__lt=cursor_id)
                )
            else:  # previous
                # Get records newer than cursor (reverse order temporarily)
                queryset = queryset.filter(
                    Q(created_at__gt=cursor_time) |
                    Q(created_at=cursor_time, id__gt=cursor_id)
                ).order_by('created_at', 'id')
        
        # Fetch one extra to determine if there are more results
        results = list(queryset[:page_size + 1])
        
        has_more = len(results) > page_size
        if has_more:
            results = results[:page_size]
        
        # If we were going backwards, reverse the results
        if cursor_data and direction == 'previous':
            results.reverse()
        
        # Generate next and previous cursors
        next_cursor = None
        previous_cursor = None
        
        if results:
            if has_more:
                last_item = results[-1]
                next_cursor = self.encode_cursor(
                    last_item.created_at,
                    last_item.id
                )
            
            if cursor_data:
                first_item = results[0]
                previous_cursor = self.encode_cursor(
                    first_item.created_at,
                    first_item.id
                )
        
        return results, next_cursor, previous_cursor, has_more    
