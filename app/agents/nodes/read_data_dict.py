import os 
import pandas as pd 
from collections import defaultdict 
import numpy as np 
import pickle 
import faiss 
import asyncio 
from sentence_transformers import SentenceTransformer 
from app.agents.state import State 

# Load model once at module level for efficiency 
_model = SentenceTransformer("all-MiniLM-L6-v2")

async def read_data_dict(state: State) -> State:
    print("Reading data dict")
    csv_path = os.path.join("app", "static", "keys.csv")

    df = await asyncio.to_thread(pd.read_csv, csv_path, encoding="latin1")

    tables = defaultdict(list)
    relations = []

    for _, row in df.iterrows():
        table = row["Table Name"].strip().lower()
        column = row["Field Name"].strip().lower()

        is_pk = str(row.get("is Primary Key", "NO")).strip().upper() == "YES"
        is_fk = str(row.get("is Foreign Key", "NO")).strip().upper() == "YES"
        ref_table = str(row.get("reference table", "")).strip().lower()
        ref_col = str(row.get("reference column", "")).strip().lower()

        col_repr = column
        if is_pk:
            col_repr += " (PK)"
        if is_fk and ref_table and ref_col:
            col_repr += f" (FK → {ref_table}.{ref_col})"
            relations.append(f"RELATION: {table}.{column} = {ref_table}.{ref_col}")

        tables[table].append(col_repr)

    schema_blocks = [
        f"TABLE: {table}; COLUMNS: " + ", ".join(cols)
        for table, cols in tables.items()
    ]

    # Generate embeddings
    embeddings = await asyncio.to_thread(
        _model.encode,
        schema_blocks,
        convert_to_numpy=True
    )
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    # Create FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    # Save index and mapping
    index_path = os.path.join("app", "agents", "vector-db", "vector_index.faiss")
    mapping_path = os.path.join("app", "agents", "vector-db", "id_to_text.pkl")

    await asyncio.to_thread(faiss.write_index, index, index_path)

    def save_mapping(path, data):
        with open(path, "wb") as f:
            pickle.dump(data, f)

    await asyncio.to_thread(save_mapping, mapping_path, schema_blocks)

    return state
