# documentation/api_docs.py
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

def approve_account_docs():
    return extend_schema(
        summary="Approve pending account",
        description="Approve an account that is in PENDING_APPROVAL status",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'notes': {
                        'type': 'string',
                        'description': 'Optional approval notes',
                        'example': 'All documents verified. Customer tier: STANDARD'
                    }
                }
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'account': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'status': {'type': 'string'},
                            'approved_at': {'type': 'string', 'format': 'date-time'}
                        }
                    }
                }
            },
            400: {'description': 'Bad request - account not in pending status'},
            404: {'description': 'Account not found'},
            403: {'description': 'Forbidden - insufficient permissions'},
        },
        tags=["Accounts - Staff"]
    )

def reject_account_docs():
    return extend_schema(
        summary="Reject pending account",
        description="Reject an account application and close it",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reason': {
                        'type': 'string',
                        'description': 'Reason for rejection (required)',
                        'example': 'KYC documents incomplete. Missing proof of address.'
                    }
                },
                'required': ['reason']
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'account': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'status': {'type': 'string'},
                            'closed_at': {'type': 'string', 'format': 'date-time'}
                        }
                    }
                }
            },
            400: {'description': 'Bad request - reason required or invalid status'},
            404: {'description': 'Account not found'},
            403: {'description': 'Forbidden - insufficient permissions'},
        },
        tags=["Accounts - Staff"]
    )
