import asyncio
from transformers import pipeline

# Load the paraphrasing model once at startup
# paraphraser = pipeline(
#     "text2text-generation",
#     model="Vamsi/T5_Paraphrase_Paws",
#     device=-1  # -1 = CPU, or set to 0 for GPU if available
# )

async def paraphrase(query: str) -> str:
    # """
    # Asynchronously paraphrase the given query using the Hugging Face T5 paraphraser model.
    # Keeps the meaning the same but rephrases naturally.
    # """
    # query = query.strip()
    # input_text = f"paraphrase: {query}"

    # # Run the blocking pipeline in a thread
    # outputs = await asyncio.to_thread(
    #     paraphraser,
    #     input_text,
    #     max_length=60,
    #     num_return_sequences=1,
    #     clean_up_tokenization_spaces=True,
    # )

    # return outputs[0]["generated_text"]

    return ""
