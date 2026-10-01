import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from langchain_openai import ChatOpenAI


KEY_VAULT_URL = os.getenv(
    "AZURE_KEY_VAULT_URL",
    "https://paymatixkeyvault.vault.azure.net/" 
)


# ==========================================
# KEY VAULT AUTHENTICATION (ONLY ONCE)
# ==========================================

credential = DefaultAzureCredential()

client = SecretClient(
    vault_url=KEY_VAULT_URL,
    credential=credential
)


# ==========================================
# SECRET HELPER
# ==========================================

def _get_secret(secret_name: str) -> str:
    env_key = secret_name.replace("-", "_").upper()

    value = os.getenv(env_key)

    if value:
        return value

    return client.get_secret(secret_name).value


# ==========================================
# LLM FACTORY
# ==========================================

# def get_llm(model_name: str = "gpt-4o-mini") -> AzureChatOpenAI:
#     endpoint = _get_secret("polga-llm-endpoint")
#     api_key = _get_secret("polga-api-key")

#     deployment_name = os.getenv(
#         "AZURE_OPENAI_DEPLOYMENT_NAME",
#         model_name
#     )
#     print(f"Endpoint: {endpoint}")
 
#     print(f"Deployment: {deployment_name}")
#     return AzureChatOpenAI(
#         azure_endpoint=endpoint,
#         api_key=api_key,
#         azure_deployment=deployment_name,
#         api_version="2024-02-01",
#         temperature=0,
#     )
def get_llm(model_name: str = "gpt-4o-mini") -> ChatOpenAI:

    endpoint = _get_secret("polga-llm-endpoint").strip().rstrip("/")
    api_key = _get_secret("polga-api-key")
    deployment_name = os.getenv(

        "AZURE_OPENAI_DEPLOYMENT_NAME",

        model_name,

    )


    # The v1-compatible endpoint must end with /openai/v1

    if not endpoint.endswith("/openai/v1"):

        endpoint = f"{endpoint}/openai/v1"


 


    return ChatOpenAI(

        base_url=endpoint,

        api_key=api_key,

        model=deployment_name,

        temperature=0,

        max_retries=2,

    )

# ==========================================
# GLOBAL LLM INSTANCE
# ==========================================

llm = get_llm()


# import os

# from azure.identity import InteractiveBrowserCredential
# from azure.keyvault.secrets import SecretClient
# from langchain_openai import AzureChatOpenAI

# KEY_VAULT_URL = os.getenv("AZURE_KEY_VAULT_URL", "https://paymatixkeyvault.vault.azure.net/")


# def _get_secret(secret_name: str) -> str:
#     env_key = secret_name.replace("-", "_").upper()
#     value = os.getenv(env_key)
#     if value:
#         return value

#     credential = InteractiveBrowserCredential()
#     client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
#     secret = client.get_secret(secret_name)
#     return secret.value


# def get_llm(model_name: str = "gpt-4o-mini") -> AzureChatOpenAI:
#     endpoint = _get_secret("polga-llm-endpoint")
#     api_key = _get_secret("polga-api-key")
#     deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", model_name)

#     return AzureChatOpenAI(
#         azure_endpoint=endpoint,
#         api_key=api_key,
#         azure_deployment=deployment_name,
#         api_version="2024-02-01",
#         temperature=0,
#     )


# llm = get_llm()

