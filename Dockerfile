FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any are needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn jinja2

# Copy the rest of the application
COPY . .

# Expose port (FastAPI default, overridden by PORT env in Spaces/Render)
EXPOSE 8501

# Command to run the application
CMD ["python", "app.py"]
