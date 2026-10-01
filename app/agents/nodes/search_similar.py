import asyncio
from sentence_transformers import SentenceTransformer
import faiss
import pickle
import numpy as np
from app.agents.state import State
import os

# Load model once at module import (expensive to reload each call)
_model = SentenceTransformer("all-MiniLM-L6-v2")

async def search_similar(state: State) -> State:
    print("searching similar")
    user_prompt = state['question']

    index_path = os.path.join("app", "agents", "vector-db", "vector_index.faiss")
    mapping_path = os.path.join("app", "agents", "vector-db", "id_to_text.pkl")

    # Run blocking I/O in threads
    index = await asyncio.to_thread(faiss.read_index, index_path)
    with open(mapping_path, "rb") as f:
        id_to_text = pickle.load(f)

    # Encode user prompt in a thread (CPU heavy)
    query_vec = await asyncio.to_thread(
        _model.encode,
        [user_prompt],
        convert_to_numpy=True
    )
    query_vec = query_vec / np.linalg.norm(query_vec, axis=1, keepdims=True)

    # Run FAISS search
    D, I = await asyncio.to_thread(index.search, query_vec, 25)

    lines = [id_to_text[idx] for idx in I[0][:10]]
    state['context'] = "\n".join(lines)
    return state
