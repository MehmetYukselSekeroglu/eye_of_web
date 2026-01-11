FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage cache
COPY requirements.txt .

# Install python dependencies opt: --no-cache-dir
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p logs uploads temp certs config

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Function to wait for a service\n\
wait_for_service() {\n\
  host="$1"\n\
  port="$2"\n\
  service="$3"\n\
  echo "Waiting for $service ($host:$port)..."\n\
  while ! timeout 1 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; do\n\
    sleep 2\n\
  done\n\
  echo "$service is ready!"\n\
}\n\
\n\
# Wait for Database\n\
wait_for_service "${DB_HOST:-postgres}" "${DB_PORT:-5432}" "PostgreSQL"\n\
\n\
# Wait for Milvus\n\
wait_for_service "${MILVUS_HOST:-milvus}" "${MILVUS_PORT:-19530}" "Milvus"\n\
\n\
# Generate config.json from environment variables\n\
echo "Generating config.json from environment variables..."\n\
python generate_config.py\n\
\n\
# Run Schema Generator (if needed)\n\
if [ "$INIT_SCHEMA" = "true" ]; then\n\
    echo "Running Milvus Schema Generator..."\n\
    python MILVUS_SCHEMA_GENERATOR.py\n\
fi\n\
\n\
# Start Application\n\
echo "Starting EyeOfWeb..."\n\
exec python run.py --mode production --workers ${GUNICORN_WORKERS:-4} --threads ${GUNICORN_THREADS:-2} --timeout ${GUNICORN_TIMEOUT:-120}\n\
' > /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

CMD ["/app/docker-entrypoint.sh"]
