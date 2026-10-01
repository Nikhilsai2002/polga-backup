import asyncio
import re
from transformers import pipeline
from app.agents.state import State
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core import llm

output_parser = StrOutputParser()

classification_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a scope classifier for PaymatiX.

    Rules:
    - If the query contains abusive language -> return ONLY 'ABUSIVE'.
    - If the query is about weather, temperature, climate, rain, humidity, seasons, or any meteorological topic -> return ONLY 'OUT_OF_SCOPE'.
    - If no abusive language is detected and the query is about credit card transactions, balances, statements,
      payments, disputes, fraud, security, account details, rewards, or anything related to banking domain -> return ONLY 'IN_SCOPE'.
    - For all other queries -> return ONLY 'OUT_OF_SCOPE'.

    Do not explain. Only output IN_SCOPE, OUT_OF_SCOPE, or ABUSIVE.
    """),
    ("user", "{query}")
])
intent_chain = classification_prompt | llm | output_parser

# Guardrail checks
BANNED_TOPICS = [
    "terrorism", "violence", "drugs", "weapons",
    "self-harm", "extremism", "hacking", "cybercrime"
]
BIAS_LABELS = [
    "gender bias", "racial bias", "religious bias", "age bias",
    "lgbtq bias", "disability bias", "socioeconomic bias", "stereotype"
]

def load_pipelines():
    tox = pipeline("text-classification", model="unitary/toxic-bert", device=-1, top_k=None, truncation=True)
    jb = pipeline("text-classification", model="ProtectAI/deberta-v3-base-prompt-injection-v2", device=-1, truncation=True)
    zsc = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=-1)
    return tox, jb, zsc

toxicity_detector, jailbreak_detector, zero_shot = load_pipelines()

# --- async wrappers for sync ML pipelines ---
async def check_toxicity(text: str, threshold: float = 0.50):
    results = await asyncio.to_thread(toxicity_detector, text)
    if isinstance(results, list) and len(results) and isinstance(results[0], list):
        results = results[0]
    labels_of_interest = {
        "toxic", "toxicity", "severe_toxicity", "insult", "threat",
        "identity_attack", "obscene", "sexual_explicit"
    }
    for r in results:
        lbl = r["label"].lower().strip()
        if lbl in labels_of_interest and r["score"] >= threshold:
            return True, f"toxicity:{lbl}:{r['score']:.2f}"
    return False, None

async def check_jailbreak(text: str, threshold: float = 0.80):
    r = (await asyncio.to_thread(jailbreak_detector, text))[0]
    lbl = r["label"].lower()
    scr = r["score"]
    if ("injection" in lbl or "attack" in lbl or lbl in {"1", "prompt_injection"}) and scr >= threshold:
        return True, f"jailbreak:{lbl}:{scr:.2f}"
    return False, None

async def check_restricted_topics(text: str, threshold: float = 0.80):
    r = await asyncio.to_thread(zero_shot, text, candidate_labels=BANNED_TOPICS, multi_label=True)
    flagged = [(lbl, scr) for lbl, scr in zip(r["labels"], r["scores"]) if scr >= threshold]
    if flagged:
        top = max(flagged, key=lambda x: x[1])
        return True, f"restricted_topic:{top[0]}:{top[1]:.2f}"
    return False, None

async def check_bias(text: str, threshold: float = 0.80):
    r = await asyncio.to_thread(zero_shot, text, candidate_labels=BIAS_LABELS, multi_label=True)
    flagged = [(lbl, scr) for lbl, scr in zip(r["labels"], r["scores"]) if scr >= threshold]
    if flagged:
        top = max(flagged, key=lambda x: x[1])
        return True, f"bias:{top[0]}:{top[1]:.2f}"
    return False, None

# leakage check returns tuple
def check_leakage(text: str):
    # Example: detect credit card numbers or PII
    if re.search(r"\b\d{16}\b", text):
        return True, "leakage:possible_card_number"
    return False, None

# --- run all guardrails ---
async def run_guardrails(text: str):
    triggers = []
    t = text.strip()
    if not t:
        return False, ["input:empty"]
    if len(t) > 4000:
        return False, ["input:too_long"]

    results = await asyncio.gather(
        check_toxicity(text),
        check_jailbreak(text),
        asyncio.to_thread(check_leakage, text),
        check_restricted_topics(text),
        check_bias(text)
    )

    for flagged, info in results:
        if flagged and info:
            triggers.append(info)

    return (len(triggers) == 0), triggers

# --- main node ---
async def classify_intent(state: State) -> dict:
    print("Classifying Intent")
    query = state['question']
    if not query:
        return {"classification": "OUT_OF_SCOPE"}

    safe, guardrail_triggers = await run_guardrails(query)

    if not safe:
        return {
            "classification": "BLOCKED_BY_GUARDRAIL",
            "guardrail_triggers": guardrail_triggers,
        }
    else:
        # If your LLM client supports async, you can await it here
        # result = (await intent_chain.ainvoke({"query": query})).strip()
        return {"classification": "IN_SCOPE"}

    return state
