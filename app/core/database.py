import os
from urllib.parse import quote_plus

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker


KEY_VAULT_URL = os.getenv(
    "AZURE_KEY_VAULT_URL",
    "https://paymatixkeyvault.vault.azure.net/" 
)

# Secret names configured in Azure Key Vault
SECRET_NAMES = {
    "host": "polga-postgres-host",
    "database": "polga-postgres-db",
    "user": "polga-postgres-user",
    "password": "polga-postgres-password",
    "port": "polga-postgres-port",
}

 

credential = DefaultAzureCredential()

client = SecretClient(
    vault_url=KEY_VAULT_URL,
    credential=credential
)


# =====================================
# Secret Helper
# =====================================

def _get_secret(secret_name: str) -> str:
    env_key = secret_name.replace("-", "_").upper()

    value = os.getenv(env_key)
    if value:
        return value

    return client.get_secret(secret_name).value


# =====================================
# Fetch Secrets
# =====================================

HOST = _get_secret(SECRET_NAMES["host"])
DATABASE = _get_secret(SECRET_NAMES["database"])
USER = _get_secret(SECRET_NAMES["user"])
PASSWORD = _get_secret(SECRET_NAMES["password"])
PORT = _get_secret(SECRET_NAMES["port"])


# =====================================
# Database URL
# =====================================

DATABASE_URL = (
    "postgresql+asyncpg://"
    f"{quote_plus(USER)}:{quote_plus(PASSWORD)}"
    f"@{HOST}:{PORT}/{DATABASE}"
)


# =====================================
# SQLAlchemy Engine
# =====================================

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


# =====================================
# FastAPI Dependency
# =====================================

async def get_db():
    async with SessionLocal() as session:
        yield session



# import os
# from urllib.parse import quote_plus

# from azure.identity import InteractiveBrowserCredential
# from azure.keyvault.secrets import SecretClient
# from fastapi import Depends
# from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
# from sqlalchemy.orm import declarative_base, sessionmaker

# KEY_VAULT_URL = os.getenv("AZURE_KEY_VAULT_URL", "https://paymatixkeyvault.vault.azure.net/")

# # Secret names already configured in Azure Key Vault
# SECRET_NAMES = {
#     "host": "polga-postgres-host",
#     "database": "polga-postgres-db",
#     "user": "polga-postgres-user",
#     "password": "polga-postgres-password",
#     "port": "polga-postgres-port",
# }


# def _get_secret(secret_name: str) -> str:
#     env_key = secret_name.replace("-", "_").upper()
#     value = os.getenv(env_key)
#     if value:
#         return value

#     credential = InteractiveBrowserCredential()
#     client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
#     secret = client.get_secret(secret_name)
#     return secret.value


# HOST = _get_secret(SECRET_NAMES["host"])
# DATABASE = _get_secret(SECRET_NAMES["database"])
# USER = _get_secret(SECRET_NAMES["user"])
# PASSWORD = _get_secret(SECRET_NAMES["password"])
# PORT = _get_secret(SECRET_NAMES["port"])

# DATABASE_URL = (
#     "postgresql+asyncpg://"
#     f"{quote_plus(USER)}:{quote_plus(PASSWORD)}@{HOST}:{PORT}/{DATABASE}"
# )

# # Create async engine
# engine = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)

# # Create session factory
# SessionLocal = sessionmaker(
#     bind=engine,
#     class_=AsyncSession,
#     expire_on_commit=False,
#     autoflush=False,
#     autocommit=False,
# )

# Base = declarative_base()


# # Dependency for FastAPI
# async def get_db():
#     async with SessionLocal() as session:
#         yield session
