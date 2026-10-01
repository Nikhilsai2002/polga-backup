import redshift_connector
import asyncio

async def redshift_connection(username: str, password: str):
    try:
        conn = await asyncio.to_thread(
            redshift_connector.connect,
            #host="ptx-cluster.cxw0uildorrw.us-east-1.redshift.amazonaws.com",
            host="localhost",
            database="mb_datamart",
            user=username,
            password=password,
            port=5439
        )
        return conn
    except Exception as e:
        print(f"Authentication failed: {e}")
        return None
