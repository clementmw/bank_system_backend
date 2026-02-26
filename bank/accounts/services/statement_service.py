from decimal import Decimal
from django.db.models import Q
from django.db import transaction 
from transactions.models import Transaction, TransactionStatus
from accounts.models import AccountStatement, StatementTransaction


def generate_account_statement(account, statement_type, period_start, period_end, generated_by):

    with transaction.atomic():

        # 1️⃣ Get all COMPLETED transactions in period
        transactions = Transaction.objects.filter(
            Q(source_account=account) | Q(destination_account=account),
            trans_status=TransactionStatus.COMPLETED,
            completed_at__date__gte=period_start,
            completed_at__date__lte=period_end
        ).order_by("completed_at")

        # 2️⃣ Determine Opening Balance
        previous_tx = Transaction.objects.filter(
            Q(source_account=account) | Q(destination_account=account),
            trans_status=TransactionStatus.COMPLETED,
            completed_at__date__lt=period_start
        ).order_by("-completed_at").first()

        if previous_tx:
            if previous_tx.source_account_id == account.id:
                opening_balance = previous_tx.source_balance_after
            else:
                opening_balance = previous_tx.destination_balance_after
        else:
            opening_balance = Decimal("0.00")

        # 3️⃣ Create statement record
        statement = AccountStatement.objects.create(
            account=account,
            statement_type=statement_type,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening_balance,
            closing_balance=opening_balance,  # temporary
            generated_by=generated_by
        )

        total_credits = Decimal("0.00")
        total_debits = Decimal("0.00")

        snapshot_rows = []

        # 4️⃣ Freeze transactions
        for tx in transactions:

            if tx.source_account_id == account.id:
                debit = tx.amount + tx.fee
                credit = Decimal("0.00")
                running_balance = tx.source_balance_after
                total_debits += debit
            else:
                debit = Decimal("0.00")
                credit = tx.amount
                running_balance = tx.destination_balance_after
                total_credits += credit

            snapshot_rows.append(
                StatementTransaction(
                    statement=statement,
                    transaction=tx,
                    transaction_date=tx.completed_at,
                    transaction_ref=tx.transaction_ref,
                    description=tx.description,
                    debit=debit,
                    credit=credit,
                    running_balance=running_balance
                )
            )

        StatementTransaction.objects.bulk_create(snapshot_rows)

        # 5️⃣ Closing balance = last running balance OR opening
        if snapshot_rows:
            closing_balance = snapshot_rows[-1].running_balance
        else:
            closing_balance = opening_balance

        statement.total_credits = total_credits
        statement.total_debits = total_debits
        statement.transaction_count = len(snapshot_rows)
        statement.closing_balance = closing_balance
        statement.save(update_fields=[
            "total_credits",
            "total_debits",
            "transaction_count",
            "closing_balance"
        ])

        return statement
