# Database Impact Analysis & Permission Requirements

Before running any script or command — especially destructive or data-modifying operations — you must analyze the potential impact on the database and the system.

## Workflow

1. **Identify the operation type** — Is the script read-only, write, or destructive (DELETE, DROP, TRUNCATE, UPDATE without WHERE, etc.)?
2. **Analyze the impact** — What data will be affected? Which tables, records, or relationships will be altered, created, or destroyed?
3. **If the impact involves data loss or modification**, you must:
   - **Pause and ask for user permission** before executing
   - **Present a clear summary** of what data will be lost or altered
   - **Wait for explicit confirmation** before proceeding

## What Requires Permission

Ask for permission before running any script that:

- **Deletes or truncates** records from the database
- **Drops or alters** tables, columns, or schema structures
- **Updates or inserts** large volumes of data (e.g., mass updates, seed data)
- **Modifies** user-facing data (e.g., changing user profiles, transaction records)
- **Runs migrations** that could roll back or cause data inconsistency
- **Clears** caches, sessions, or temporary data that may be needed

## What Does NOT Require Permission

- Read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN)
- Running the application or server locally
- Running tests that use isolated test databases
- Non-destructive configuration changes (e.g., environment variables, config files)

## How to Present Impact to the User

When permission is required, clearly communicate:

```
⚠️ This script will modify/delete data. Details:

Affected tables: [table names]
Operation type: [e.g., DELETE FROM users WHERE ...]
Records affected: [approximate or exact count]
Risk level: [Low / Medium / High]

Continue? (y/n)
```

## Rationale

- **Prevents accidental data loss** — Many scripts can have unintended consequences
- **Maintains user trust** — Users stay in control of their data
- **Encourages careful execution** — Forces a pause-and-review step before irreversible actions
- **Audit trail** — Makes it clear when and why data changes were made

## Examples

### Bad — Running destructive queries without checking

```bash
# Just runs the migration
python3 migrate.py
```

### Good — Analyzing impact first

```bash
# 1. Inspect the migration file
cat migrate.py

# 2. Preview what will be affected
python3 migrate.py --dry-run

# 3. Present impact to user and ask permission
echo "⚠️ This migration will DELETE 1,234 records from 'sessions' table."
echo "Continue? (y/n)"

# 4. Only proceed after confirmation
if [ "$answer" = "y" ]; then
    python3 migrate.py
fi
```