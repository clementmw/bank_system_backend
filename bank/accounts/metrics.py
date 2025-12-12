from prometheus_client import Counter

# Counter for created accounts
accounts_created_total = Counter(
    "accounts_created_total",
    "Total number of accounts created"
)

# Counter for account creation failures (optional but useful)
accounts_creation_failed_total = Counter(
    "accounts_creation_failed_total",
    "Total number of failed account creation attempts"
)

accounts_approved_total = Counter(
    'accounts_approved_total',
    'Total number of accounts approved'
)

accounts_rejected_total = Counter(
    'accounts_rejected_total',
    'Total number of accounts rejected'
)