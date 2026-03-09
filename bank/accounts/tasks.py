from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
import logging
from math import ceil
from weasyprint import HTML
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

PAGE_SIZE = 500

@shared_task(queue="low", bind=True, max_retries=3, default_retry_delay=300)
def generate_statement_pdf(self,statement_id):
    from accounts.models import AccountStatement
    try:
        statement = AccountStatement.objects.select_related("account").get(id=statement_id)

        total_transactions = statement.statement_transactions.count()
        total_pages = ceil(total_transactions / PAGE_SIZE)

        all_pages_html = ""

        for page in range(total_pages):

            start = page * PAGE_SIZE
            end = start + PAGE_SIZE

            transactions = (
                statement.statement_transactions
                .all()
                .order_by("transaction_date")[start:end]
            )

            page_html = render_to_string(
                "statements/statement_page.html",
                {
                    "statement": statement,
                    "customer_name":statement.account.customer.user.get_full_name(),
                    "address":statement.account.customer.address,
                    "country":statement.account.customer.country,
                    "city":statement.account.customer.city,
                    "transactions": transactions,
                    "page_number": page + 1,
                    "total_pages": total_pages,
                }
            )

            all_pages_html += page_html

        pdf_file = HTML(string=all_pages_html).write_pdf()

        filename = f"statement_{statement.period_start}.pdf"

        statement.pdf_file.save(filename, ContentFile(pdf_file))
        statement.save(update_fields=["pdf_file"])
    except Exception as e:
        logger.exception(f"Failed to generate statement PDF for {statement_id}")
        raise self.retry(exc=e)
