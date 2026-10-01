import pandas as pd
from app.agents.state import SQLValidation
from app.agents.utils import read_data_dictionary
from typing import Dict, Set
from sqlglot import parse_one, expressions as exp
from sqlglot.errors import ParseError
from sentence_transformers import SentenceTransformer, util
from app.core.llm_loader import llm
import os, asyncio

async def sql_validation(state: SQLValidation) -> SQLValidation:
    sql_query = state["query"].strip().rstrip(";")
    if not sql_query.lower().startswith("select"):
        state["valid_sql"] = False
        return state

    # run blocking read in thread
    df = await asyncio.to_thread(read_data_dictionary)
    schema: Dict[str, Set[str]] = {}
    for _, row in df.iterrows():
        table = str(row["Table Name"]).strip().lower()
        field = str(row["Field Name"]).strip().lower()
        schema.setdefault(table, set()).add(field)

    try:
        tree = parse_one(sql_query, read="redshift")

        tables = [t.name.lower() for t in tree.find_all(exp.Table)]
        alias_map = {t.alias.lower(): t.name.lower() for t in tree.find_all(exp.Table) if t.alias}
        columns = [(c.name.lower(), c.table.lower() if c.table else None) for c in tree.find_all(exp.Column)]

        alias_columns = set()
        for select_expr in tree.expressions:
            if isinstance(select_expr, exp.Alias):
                alias_columns.add(select_expr.alias.lower())

        for col, tbl in columns:
            if tbl:
                real_table = alias_map.get(tbl, tbl)
                if real_table not in schema:
                    print(f"❌ Unknown table '{real_table}' (alias was '{tbl}')")
                    state["valid_sql"] = False
                    return state
                if col not in schema[real_table]:
                    print(f"❌ Unknown column '{col}' in table '{real_table}'")
                    state["valid_sql"] = False
                    return state
            else:
                if col in alias_columns:
                    continue
                found = any(col in schema[t] for t in tables)
                if not found:
                    print(f"❌ Unknown unqualified column '{col}'")
                    state["valid_sql"] = False
                    return state

        state["valid_sql"] = True

        # Extract columns and alias map
        parsed = tree
        columns = []
        for col in parsed.find_all(exp.Column):   # <-- pass the class, not a string
            table = col.table  # alias or table name (fa, de, or None)
            name = col.name    # column name
            columns.append((table, name))

        # print(columns)

        # Extract alias → table mapping
        alias_map = {}
        for table in parsed.find_all(exp.Table):
            real_name = table.name.upper()        # FACTACCOUNTSNAPSHOT_FINAL, DIMEXTERNALSTATUS
            alias = table.alias                  # fa, de
            if alias:
                alias_map[alias] = real_name
            else:
                alias_map[real_name] = real_name  # handle tables without alias

        all_tables = set(alias_map.values())
        cols = []
        for col in parsed.find_all(exp.Column):
            alias = col.table
            name = col.name.upper()
            table = alias_map.get(alias, None)
            if table is None:
                for t in all_tables:
                    cols.append((t, name))
            else:
                cols.append((table, name))

        df_cols = pd.DataFrame(cols, columns=["Table Name", "Field Name"]).drop_duplicates().reset_index(drop=True)

        file_path = os.path.join("app", "static", "keys1.csv")
        dd = await asyncio.to_thread(pd.read_csv, file_path)
        dd["Table Name"] = dd["Table Name"].str.upper()
        dd["Field Name"] = dd["Field Name"].str.upper()

        used = pd.DataFrame(cols, columns=["Table Name", "Field Name"])
        desc_subset = dd.merge(used, on=["Table Name", "Field Name"], how="inner")

        context = "Here are the column descriptions:\n"
        for _, row in desc_subset.iterrows():
            context += f"- {row['Table Name']}.{row['Field Name']}: {row['Description']}\n"

        prompt = f"""
        Given the following SQL query:

        {sql_query}

        And the following column descriptions:

        {context}

        Explain in plain English what this SQL query does who doesnt have any knowledge of schema of tables so DONT ellaborate that (STRICTLY DONT GIVE ANY TABLE NAMES). Only give me in 2-3 lines
        """

        # If llm supports async:
        # response = await llm.ainvoke(prompt)
        # Otherwise:
        response = await asyncio.to_thread(llm.invoke, prompt)
        s1 = response.content

        s2 = state['question']
        r2_prompt = f"""
        Sentence : {s2}
        Ellaborate this sentence of what all should be there in sql query (STRICTLY DONT GIVE ANY SQL QUERY).
        Give 2-3 lines only as plain English as a paragraph and the result should start like The query contains/retrieve...
        """
        r2 = await asyncio.to_thread(llm.invoke, r2_prompt)

        model = SentenceTransformer("all-MiniLM-L6-v2")

        emb1 = await asyncio.to_thread(model.encode, s1, convert_to_tensor=True)
        emb2 = await asyncio.to_thread(model.encode, r2.content, convert_to_tensor=True)

        similarity = util.cos_sim(emb1, emb2)
        print(similarity.item())
        state["accuracy"] = similarity.item() * 100
        return state

    except ParseError as e:
        print("❌ SQL parsing error:", e)
        state["valid_sql"] = False
        return state
    except Exception as e:
        print("❌ General SQL validation error:", e)
        state["valid_sql"] = False
        return state
