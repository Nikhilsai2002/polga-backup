# create_polga_tables.py

from azure.identity import InteractiveBrowserCredential
from azure.keyvault.secrets import SecretClient

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
    text
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine import URL


# ==========================================================
# KEY VAULT CONFIGURATION
# ==========================================================

VAULT_URL = "https://paymatixkeyvault.vault.azure.net/"

credential = InteractiveBrowserCredential()

kv_client = SecretClient(
    vault_url=VAULT_URL,
    credential=credential
)

# ==========================================================
# FETCH DB SECRETS
# ==========================================================

HOST = kv_client.get_secret("polga-postgres-host").value
DATABASE = kv_client.get_secret("polga-postgres-db").value
USER = kv_client.get_secret("polga-postgres-user").value
PASSWORD = kv_client.get_secret("polga-postgres-password").value
PORT = kv_client.get_secret("polga-postgres-port").value

print("✅ Secrets fetched successfully from Key Vault")
 

# ==========================================================
# SQLALCHEMY CONNECTION
# ==========================================================

db_url = URL.create(
    drivername="postgresql+psycopg2",
    username=USER,
    password=PASSWORD,
    host=HOST,
    port=int(PORT),
    database=DATABASE,
)

engine = create_engine(
    db_url,
    echo=True,
    connect_args={
        "sslmode": "require"
    }
)

Base = declarative_base()

# ==========================================================
# ANALYSIS TABLE
# ==========================================================

class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    created_by = Column(String(255), index=True)
    created_at = Column(String, server_default=func.now())
    updated_at = Column(DateTime)


# ==========================================================
# CONVERSATION TABLE
# ==========================================================

class Conversation(Base):
    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True, index=True)

    analysis_id = Column(
        Integer,
        ForeignKey("analysis.id")
    )

    user_question = Column(Text)
    sql_generated = Column(Text)
    execution_output = Column(Text)
    summary = Column(Text)

    created_at = Column(
        String,
        server_default=func.now()
    )


# ==========================================================
# USER SESSIONS TABLE
# ==========================================================

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(
        String(255),
        index=True
    )

    session_id = Column(
        String(255),
        unique=True,
        index=True
    )

    created_at = Column(
        String,
        server_default=func.now()
    )


# ==========================================================
# CREATE TABLES
# ==========================================================

try:

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))  

   

    Base.metadata.create_all(engine)

finally:
    if conn:
        conn.close()

    print("connection closed.")      
