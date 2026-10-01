import io
import os

import pandas as pd
from azure.identity import DefaultAzureCredential 
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient


KEY_VAULT_URL = os.getenv(
    "AZURE_KEY_VAULT_URL",
    "https://paymatixkeyvault.vault.azure.net/"
)


 

kv_credential = DefaultAzureCredential()

kv_client = SecretClient(
    vault_url=KEY_VAULT_URL,
    credential=kv_credential
)


def _get_secret(secret_name: str) -> str:
    env_key = secret_name.replace("-", "_").upper()

    value = os.getenv(env_key)

    if value:
        return value

    return kv_client.get_secret(secret_name).value


 

def read_data_dictionary():
    try:
        print("Fetching blob configuration from Key Vault...")

        account_url = _get_secret("polga-blob-accounturl")
        container_name = _get_secret("polga-blob-container")
        blob_name = _get_secret("polga-blob-file")

        print("Blob configuration fetched successfully")

         

        blob_credential = InteractiveBrowserCredential()

        blob_service_client = BlobServiceClient(
            account_url=account_url,
            credential=blob_credential
        )

        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )

        print("Downloading file from Blob Storage...")

        data = blob_client.download_blob().readall()

        df = pd.read_csv(
            io.BytesIO(data),
            encoding="latin1"
        )

        required_cols = [
            "Table Name",
            "Field Name",
            "Description",
            "Business Name"
        ]

        if not all(col in df.columns for col in required_cols):
            print("Required columns missing in CSV.")
            return []

        print("CSV loaded successfully")

        return (
            df[required_cols]
            .dropna(how="all")
            .reset_index(drop=True)
        )

    except Exception as e:
        print(f"Error reading blob-backed data dictionary: {str(e)}")
        return []