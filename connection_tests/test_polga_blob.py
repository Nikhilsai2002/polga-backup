import io
import pandas as pd
from azure.identity import InteractiveBrowserCredential
from azure.storage.blob import BlobServiceClient


def read_data_dictionary():
    try:
        print("Connecting to Azure Blob Storage...")

        credential = InteractiveBrowserCredential()

        client = BlobServiceClient(
            account_url="https://adwinputfiles.blob.core.windows.net",
            credential=credential
              )

        blob_client = client.get_blob_client(
            container="polga-test-container",
            blob="keys1.csv"
        )
 
        print("Downloading CSV...")

        # Download blob content
        data = blob_client.download_blob().readall()

        # Convert bytes -> DataFrame
        df = pd.read_csv(io.BytesIO(data))

        print("\nCSV Loaded Successfully.")
        print(f"Total Rows: {len(df)}")
        print(f"Total Columns: {len(df.columns)}")

        print("\nColumns:")
        print(df.columns.tolist())

        required_cols = [
            "Table Name",
            "Field Name",
            "Description",
            "Business Name"
        ]

        if not all(col in df.columns for col in required_cols):
            print("\nRequired columns missing in CSV.")
            return []

        result_df = df[required_cols]

        print("\nFirst 5 Rows:")
        print(result_df.head())

        return result_df

    except Exception as e:
        print(f"\nError: {str(e)}")
        return []


if __name__ == "__main__":
    df = read_data_dictionary()

    if isinstance(df, pd.DataFrame):
        print("\nDataFrame Shape:", df.shape)