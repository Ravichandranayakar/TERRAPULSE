FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies if required for ML packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies list
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Expose the port (Render provides $PORT dynamically, but defaults to 10000)
EXPOSE 10000

# Command to run the Uvicorn server using the PORT environment variable
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
