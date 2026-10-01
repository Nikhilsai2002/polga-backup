import asyncio
from sqlalchemy import text

from app.core.database import engine  # Replace with your actual file name


async def test_database():
    try:
        print("Testing database connection...")

        async with engine.connect() as conn:
            # Test connection
            result = await conn.execute(text("SELECT version();"))

            print("\n✅ DATABASE CONNECTED SUCCESSFULLY")
            print(result.scalar())

            # Get table names
            tables = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))

            table_list = [row[0] for row in tables.fetchall()]

            print("\n📋 TABLES FOUND:")
            for table in table_list:
                print(f" - {table}")

            if table_list:
                first_table = table_list[0]

                print(f"\n🔎 SAMPLE DATA FROM: {first_table}")

                sample = await conn.execute(
                    text(f'SELECT * FROM "{first_table}" LIMIT 5')
                )

                rows = sample.fetchall()

                if rows:
                    for row in rows:
                        print(row)
                else:
                    print("No rows found.")

    except Exception as e:
        print("\n❌ CONNECTION FAILED")
        print(str(e))


if __name__ == "__main__":
    asyncio.run(test_database())