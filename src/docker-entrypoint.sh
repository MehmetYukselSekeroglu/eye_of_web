#!/bin/bash
set -e

wait_for_service() {
  host="$1"
  port="$2"
  service="$3"
  echo "Waiting for $service ($host:$port)..."
  while ! timeout 1 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; do
    sleep 2
  done
  echo "$service is ready!"
}

wait_for_service "${DB_HOST:-postgres}" "${DB_PORT:-5432}" "PostgreSQL"

wait_for_service "${MILVUS_HOST:-milvus}" "${MILVUS_PORT:-19530}" "Milvus"

echo "Generating config.json from environment variables..."
python generate_config.py

if [ "$INIT_SCHEMA" = "true" ]; then
    echo "Running Milvus Schema Generator..."
    python MILVUS_SCHEMA_GENERATOR.py
fi

echo "Starting EyeOfWeb..."
exec python run.py --mode production --workers ${GUNICORN_WORKERS:-4} --threads ${GUNICORN_THREADS:-2} --timeout ${GUNICORN_TIMEOUT:-120}

