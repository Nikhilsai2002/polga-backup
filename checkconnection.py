import psycopg2
from psycopg2 import OperationalError

def test_redshift_connection(host, port, dbname, user, password):
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        print("✅ Connection to Redshift successful!")
        conn.close()
    except OperationalError as e:
        print("❌ Failed to connect to Redshift.")
        print(f"Error: {e}")

# Example usage — replace with your actual credentials
test_redshift_connection(
    #host="ptx-cluster.cxw0uildorrw.us-east-1.redshift.amazonaws.com",
    #host="ptx-integration-db.cxw0uildorrw.us-east-1.redshift.amazonaws.com",
    host="localhost",
    port="5439",
    dbname="ptx_dwh_db",
    user="ptx_nlp_user",
    password="Pass@123"
)

 