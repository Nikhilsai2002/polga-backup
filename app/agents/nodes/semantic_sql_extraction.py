import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import pickle
from app.agents.state import State
import os
import asyncio

async def semantic_sql_extraction(state: State) -> State:
    print("Searching FAISS index for related prompts...")

    file_path = os.path.join("app", "static", "PE_PAIRS_TEST.csv")

    # Run blocking pandas read in a thread
    pe_pairs = await asyncio.to_thread(pd.read_csv, file_path, dtype=str)
    queries = pe_pairs['Query Final'].tolist()
    prompts = pe_pairs['Prompt'].dropna().astype(str).tolist()

    # Load model (you may want to cache this globally instead of reloading each call)
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Run embedding in a thread
    prompt_embeddings = await asyncio.to_thread(
        model.encode, prompts, convert_to_numpy=True
    )
    prompt_embeddings = prompt_embeddings / np.linalg.norm(prompt_embeddings, axis=1, keepdims=True)

    embedding_dim = prompt_embeddings.shape[1]
    index = faiss.IndexFlatIP(embedding_dim)
    index.add(prompt_embeddings)

    user_prompt = state['question']

    # Save index and mapping (blocking I/O → thread)
    index_path = os.path.join("app", "agents", "vector-db", "pe_pairs_index.faiss")
    map_path = os.path.join("app", "agents", "vector-db", "pe_pairs_id_to_text_and_query.pkl")
    top_k = 15

    await asyncio.to_thread(faiss.write_index, index, index_path)
    id_to_prompt_query_map = {i: {'prompt': prompt, 'query': queries[i]} for i, prompt in enumerate(prompts)}

    await asyncio.to_thread(
        pickle.dump, id_to_prompt_query_map, open(map_path, "wb")
    )

    # Encode user prompt
    user_embedding = await asyncio.to_thread(
        model.encode, [user_prompt], convert_to_numpy=True
    )
    user_embedding = user_embedding / np.linalg.norm(user_embedding, axis=1, keepdims=True)

    # Reload index and mapping
    index = await asyncio.to_thread(faiss.read_index, index_path)
    scores, indices = index.search(user_embedding, top_k)

    with open(map_path, "rb") as f:
        id_to_prompt_query_map = pickle.load(f)

    matched_prompts = [id_to_prompt_query_map[i]['prompt'] for i in indices[0]]
    matched_queries = [id_to_prompt_query_map[i]['query'] for i in indices[0]]
    matched_scores = scores[0]

    matched_queries = matched_queries[:5]
    suggestions = matched_prompts[12:]

    # remove duplicates while preserving order
    seen = set()
    distinct_queries = []
    for q in matched_queries:
        if q not in seen:
            seen.add(q)
            distinct_queries.append(q)

    state["top_5_queries"] = distinct_queries
    state['suggestions'] = suggestions

    return state
