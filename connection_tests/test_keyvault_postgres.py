import psycopg2
from psycopg2 import sql

from azure.identity import InteractiveBrowserCredential
from azure.keyvault.secrets import SecretClient


# ==========================
# Key Vault Configuration
# ==========================

VAULT_URL = "https://paymatixkeyvault.vault.azure.net/"

credential = InteractiveBrowserCredential()

kv_client = SecretClient(
    vault_url=VAULT_URL,
    credential=credential
)

# Fetch secrets from Key Vault
HOST = kv_client.get_secret("polga-postgres-host").value
DATABASE = kv_client.get_secret("polga-postgres-db").value
USER = kv_client.get_secret("polga-postgres-user").value
PASSWORD = kv_client.get_secret("polga-postgres-password").value
PORT = kv_client.get_secret("polga-postgres-port").value

print("Secrets fetched successfully from Key Vault")
print(f"HOST: {HOST}")
conn = None
cursor = None

try:
    conn = psycopg2.connect(
        host=HOST,
        database=DATABASE,
        user=USER,
        password=PASSWORD,
        port=PORT,
        sslmode="require"
    )

    print("\nConnected to PostgreSQL!")

    cursor = conn.cursor()

    # Get all tables
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)

    tables = cursor.fetchall()

    print("\nTables in database:")

    if not tables:
        print("No tables found.")
    else:
        for table in tables:
            print(f" - {table[0]}")

    table_name = tables[0][0]

    print(f"\nSample data from '{table_name}'")

    query = sql.SQL(
        "SELECT * FROM {} LIMIT 10"
    ).format(
        sql.Identifier(table_name)
    )

    cursor.execute(query)

    rows = cursor.fetchall()

    column_names = [
        description[0]
        for description in cursor.description
    ]

    print("\nColumns:")
    print(column_names)

    print("\nRows:")

    if rows:
        for row in rows:
            print(row)
    else:
        print("No data found in table.")

except psycopg2.Error as error:
    print("\nPostgreSQL Error:")
    print(error)

except Exception as error:
    print("\nUnexpected Error:")
    print(error)

finally:
    if cursor:
        cursor.close()

    if conn:
        conn.close()

    print("\nConnection closed.")