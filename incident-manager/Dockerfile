# incident-manager/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set default environment settings
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose container port
EXPOSE 8080

# Run uvicorn on container startup
CMD ["sh", "-c", "uvicorn api.main:app --host $HOST --port $PORT"]
