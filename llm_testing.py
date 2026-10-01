from app.core.llm_loader import _get_secret, llm

print("Testing Azure OpenAI connection...\n")
print(_get_secret("polga-llm-endpoint"))
print(_get_secret("polga-api-key"))

try:
    response = llm.invoke(
        "Reply with exactly: Azure OpenAI Connection Successful"
    )

    print("✅ LLM Connected Successfully\n")

    print("Response:")
    print(response.content)

except Exception as e:
    print("\n❌ LLM Connection Failed\n")
    print(str(e))