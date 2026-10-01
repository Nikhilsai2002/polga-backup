import io
import pandas as pd

from azure.identity import InteractiveBrowserCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient


def read_data_dictionary():
    try:
        print("Authenticating...")

        credential = InteractiveBrowserCredential()

        # Key Vault URL
        vault_url = "https://paymatixkeyvault.vault.azure.net/"

        kv_client = SecretClient(
            vault_url=vault_url,
            credential=credential
        )

        print("Fetching secrets from Key Vault...")

        account_url = kv_client.get_secret(
            "polga-blob-accounturl"
        ).value

        container_name = kv_client.get_secret(
            "polga-blob-container"
        ).value

        blob_name = kv_client.get_secret(
            "polga-blob-file"
        ).value

        print("✅ Secrets fetched successfully")

        blob_service_client = BlobServiceClient(
            account_url=account_url,
            credential=credential
        )

        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        print("Account URL :", account_url)
        
        print("Container :", container_name)
        
        print("Blob Name :", blob_name)
        print("Checking blob...")

        props = blob_client.get_blob_properties()

        print(f"Blob Name : {props.name}")
        print(f"Blob Size : {props.size} bytes")

        print("Reading CSV...")

        data = blob_client.download_blob().readall()

        df = pd.read_csv(io.BytesIO(data))

        print("\n✅ CSV Loaded Successfully")
        print("\nFirst 5 Rows:\n")

        print(df.head())

        return df

    except Exception as e:
        print(f"\nError: {e}")
        return None


if __name__ == "__main__":
    read_data_dictionary()