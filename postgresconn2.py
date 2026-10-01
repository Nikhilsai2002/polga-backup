import psycopg2
from psycopg2 import sql

HOST = "paymatixdatabase.postgres.database.azure.com"
DATABASE = "paymatixDB001"
USER = "developer_user"
PASSWORD = "WelcomeHexa@123"
PORT = 5432

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

    print("Connected to PostgreSQL!")

    cursor = conn.cursor()

    # Get all tables from the public schema
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

        # Fetch data from the first table
        table_name = tables[0][0]

        print(f"\nSample data from '{table_name}':")

        # Safely use the table name in the SQL query
        query = sql.SQL("SELECT * FROM {} LIMIT 10").format(
            sql.Identifier(table_name)
        )

        cursor.execute(query)

        rows = cursor.fetchall()

        # Print column names
        column_names = [description[0] for description in cursor.description]
        print("Columns:", column_names)

        # Print rows
        if rows:
            for row in rows:
                print(row)
        else:
            print("No data found in this table.")

except psycopg2.Error as error:
    print("PostgreSQL error:")
    print(error)

except Exception as error:
    print("Unexpected error:")
    print(error)

finally:
    if cursor is not None:
        cursor.close()

    if conn is not None:
        conn.close()

    print("\nConnection closed.")
 