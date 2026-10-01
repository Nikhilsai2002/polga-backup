import pandas as pd
from rapidfuzz import process, utils
import os
from app.agents.state import State
import asyncio

async def get_associated_query(state: State) -> State:
    # 1. Load the CSV file
    statement = state['question']
    file_path = os.path.join("app", "static", "PE_PAIRS_TEST.csv")
    df = await asyncio.to_thread(pd.read_csv, file_path, dtype=str)

    # 2. Preprocess: Ensure columns are strings and lowercase for matching
    # We use rapidfuzz's internal processor for better normalization
    df['prompt_clean'] = df['Prompt'].astype(str).str.lower().str.strip()
    clean_statement = statement.lower().strip()

    # 3. Find the best match
    # extractOne returns: (matched_string, score, index)
    match_results = process.extractOne(
        clean_statement, 
        df['prompt_clean'],
        processor=utils.default_process
    )

    if match_results:
        best_match_str, score, index = match_results
        
        # You can set a threshold (e.g., if score < 70, it's a bad match)
        if score > 90:
            state['sql'] = df.iloc[index]['Query Final']
            return state
            
    return state