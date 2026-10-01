import asyncio
import os
import re
import pandas as pd
from collections import defaultdict
from sqlglot import parse_one, expressions as exp
from app.core.llm_loader import llm
from app.agents.state import State

async def trim_data_dictionary_and_generate_sql(state: State) -> State: 
    u_query = state["question"]
    res = []

    for s in state["top_5_queries"]:
        print("Trimming Data Dict and Generating SQL")   
        tab_list = []
        sql_query = s

        # Parse SQL synchronously (fast enough)
        tree = parse_one(sql_query, read="redshift")
        tables = [t.name.lower() for t in tree.find_all(exp.Table)]
        tab_list.extend(tables)
        print(tab_list)
        
        file_path = os.path.join("app", "static", "keys1.csv")
        # Run blocking pandas read in a thread
        dd = await asyncio.to_thread(pd.read_csv, file_path, encoding="utf-8")
        dd.columns = dd.columns.str.strip()
        print(dd.columns.tolist())
        dd["Table Name"] = dd["Table Name"].str.lower()
        dd["Field Name"] = dd["Field Name"].str.lower()

        used = pd.DataFrame(tab_list, columns=["Table Name"])
        desc_subset = dd.merge(used, on=["Table Name"], how="inner")
        
        df = desc_subset

        tables_dict = defaultdict(list)
        relations = []

        for _, row in df.iterrows():
            table = row["Table Name"].strip().lower()
            column = row["Field Name"].strip().lower()

            is_pk = str(row.get("is Primary Key", "NO")).strip().upper() == "YES"
            is_fk = str(row.get("is Foreign Key", "NO")).strip().upper() == "YES"
            ref_table = str(row.get("reference table", "")).strip().lower()
            ref_col = str(row.get("reference column", "")).strip().lower()
            business_name = str(row.get("Business Name", "")).strip()
            descr = str(row.get("Description", "")).strip()

            col_repr = column
            if is_pk:
                col_repr += " (PK)"
            if is_fk and ref_table and ref_col:
                col_repr += f" (FK → {ref_table}.{ref_col})"
                relations.append(f"RELATION: {table}.{column} = {ref_table}.{ref_col}")
            col_repr += f" | BUSINESS NAME: {business_name} | DESCRIPTION: {descr}"

            tables_dict[table].append(col_repr)

        schema_blocks = []
        for table, cols in tables_dict.items():
            block = f"TABLE: {table}; COLUMN NAME: " + ", ".join(cols)
            schema_blocks.append(block)
        
        print("Generating SQL query...")
        context_text = "\n".join(map(str, schema_blocks))

        prompt = f"""You are an SQL query generator. Use ONLY the provided schema and relations to generate SQL query for the user prompt.

            SCHEMA CONTEXT:
            {context_text}

            USER QUESTION:
            {u_query}

            SQL QUERY:
            {sql_query}
        """

        system_message = (
            "PLEASE STRICTLY give me final executable SQL query ONLY after correcting it. I dont want any correction details. "
            "STRICTLY use ONLY the provided context schema for generating queries. "
            "STRICTLY USE the correct column and table names as provided in the schema context. "
            "When making joins pay close attention to the foreign key relationships provided in the schema context. "
            "FK relationships are the ONLY valid joins you can make. "
            "The FROM and JOIN tables must be relevant to the user's query and MUST exist in the schema. "
            "STRICTLY DO NOT create, infer, assume, or rename any tables, columns, or relationships not explicitly listed in the schema. "
            "STRICTLY DO NOT map absent columns to existing schema columns even if they seem similar. "
            "Use the GROUP BY, WHERE, AND HAVING clause wherever it seems to be relevant to the prompt. "
            "Use the RELATION lines provided to determine joins; NEVER invent join conditions. "
            "STRICTLY use the Business Name as the alias for each column in the SELECT clause. "
            "If the query requires unavailable data, respond EXACTLY with: NOT PRESENT. "
            "Output MUST STRICTLY be a single raw executable SQL query with no additional information or explanation."
        )

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        # If llm supports async:
        # response = await llm.ainvoke(messages)
        # Otherwise run in thread:
        response = await asyncio.to_thread(llm.invoke, messages)

        pattern = r"(SELECT[\s\S]*?;)"
        match = re.search(pattern, response.content, re.DOTALL | re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            res.append(query)
    
    state["top_5_queries"] = res
    return state
