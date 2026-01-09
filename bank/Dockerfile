FROM python:3.11

# Set work directory
WORKDIR /app

# to handle wesyprint issues
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libcairo2 \
       libpango-1.0-0 \
       libpangocairo-1.0-0 \
       libgdk-pixbuf-xlib-2.0-0 \
       libffi-dev \
       shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

ENV PYTHONUNBUFFERED=1

