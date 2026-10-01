from agents import State
import pandas as pd
from app.agents.state import State

def read_table_dict(state: State) -> State:
    try:
        df = pd.read_csv('Table Description.csv')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv('Table Description.csv', encoding='latin1')
        except Exception as e:
            print(f"Error reading a file {str(e)}")
 
    table_desc = [
        f"TABLE: {row['Table name'].lower()}"
        for _, row in df.iterrows()
    ]
    return state 