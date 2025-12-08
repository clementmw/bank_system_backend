FROM python:3.11

# Set work directory
WORKDIR /app



# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Expose port
EXPOSE 8000

# Run Django using Gunicorn
CMD ["gunicorn", "bank.wsgi:application", "--bind", "0.0.0.0:8000"]
