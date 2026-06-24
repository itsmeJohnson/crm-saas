#!/bin/bash
set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Error: Please specify the backup file path to restore."
    echo "Usage: $0 /path/to/backup.sql.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Load PG credentials or fallback to compose defaults
DB_HOST="${POSTGRES_SERVER:-db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
DB_NAME="${POSTGRES_DB:-crm}"

echo "Preparing to restore database '$DB_NAME' from '$BACKUP_FILE'..."
echo "WARNING: This will overwrite existing data. Proceeding in 3 seconds..."
sleep 3

export PGPASSWORD="$DB_PASSWORD"

# Drop schema/recreate (optional, but standard pg_restore/psql dump requires it or runs inside transact)
# We stream directly. If pg_dump used clean parameters or drops it'll execute it.
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME"

echo "Database restore completed successfully."
