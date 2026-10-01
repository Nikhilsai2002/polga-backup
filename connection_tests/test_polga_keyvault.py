from azure.identity import InteractiveBrowserCredential
from azure.keyvault.secrets import SecretClient

# Replace with your vault URL
VAULT_URL = "https://paymatixkeyvault.vault.azure.net/" 

credential = InteractiveBrowserCredential()

client = SecretClient(
    vault_url=VAULT_URL,
    credential=credential
)

secret = client.get_secret("polga-test-secret")

print("Secret Name :", secret.name)
print("Secret Value:", secret.value)