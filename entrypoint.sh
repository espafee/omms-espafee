#!/bin/sh
set -e

attempt=0
until python -c "import os, socket; host=os.getenv('POSTGRES_HOST', 'db'); port=int(os.getenv('POSTGRES_PORT', '5432')); socket.create_connection((host, port), timeout=2).close()"
do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Database is not reachable"
    exit 1
  fi
  sleep 2
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
