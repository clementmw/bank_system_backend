from prometheus_client import Counter,Histogram


# Counter for transactions processed
transactions_processed_total = Counter(
    'transactions_processed_total',
    'Total number of transactions processed',
    ['transaction_type']
)

# Histogram for transaction processing time
transaction_processing_time_seconds = Histogram(
    'transaction_processing_time_seconds',
    'Time spent processing a transaction',
    ['transaction_type']
)
# Counter for failed transactions
transactions_failed_total = Counter(
    'transactions_failed_total',
    'Total number of failed transactions',
    ['transaction_type', 'failure_reason']
)
# Counter for successful transactions
transactions_successful_total = Counter(
    'transactions_successful_total',
    'Total number of successful transactions',
    ['transaction_type']
)
# counter for failed  fraud detection
fraud_detection_failed_total = Counter(
    'fraud_detection_failed_total',
    'Total number of failed fraud detections',
    ['fraud_type', 'failure_reason']
)
# fraud check duration
fraud_check_duration_seconds = Histogram(
    'fraud_check_duration_seconds',
    'Time spent checking for fraud',
    ['fraud_type']
)