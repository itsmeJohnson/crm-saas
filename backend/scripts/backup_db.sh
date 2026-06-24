#!/bin/bash
set -eo pipefail

# Load PG credentials or fallback to compose defaults
DB_HOST="${POSTGRES_SERVER:-db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
DB_NAME="${POSTGRES_DB:-crm}"
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"

# Create backup directory if it does not exist
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_${DB_NAME}_$TIMESTAMP.sql.gz"

echo "Starting PostgreSQL backup for database '$DB_NAME'..."

# Export password to environment for pg_dump without interactive prompt
export PGPASSWORD="$DB_PASSWORD"

# Execute pg_dump and compress the output stream
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"

echo "Backup created successfully: $BACKUP_FILE"

# Upload backup to DigitalOcean Spaces bucket and rotate
echo "Uploading backup to DigitalOcean Spaces..."
python "$(dirname "$0")/upload_backup.py" "$BACKUP_FILE"

# Manage retention - remove local files older than 7 days
echo "Cleaning up local backups older than 7 days..."
find "$BACKUP_DIR" -type f -name "backup_${DB_NAME}_*.sql.gz" -mtime +7 -exec rm -f {} \;

echo "Database backup routine completed."
