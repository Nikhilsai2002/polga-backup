import asyncio
import re
from app.agents.state import State
from app.utils.redshift_connection import redshift_connection as authenticate_redshift_user

def clean_line(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Replace non-breaking and zero-width spaces
    text = text.replace('\u00A0', ' ').replace('\u200B', ' ')
    # Collapse multiple spaces and strip edges
    text = re.sub(r'\s+', ' ', text).strip()
    return text

async def execute_sql(state: State) -> State:
    print("Executing SQL")
    print(state['sql'])
    raw_sql = state['sql']
    cleaned_sql = clean_line(raw_sql)
    #cleaned_sql="""SELECT FILTERREPORTINGPERIOD as "Reporting Period",   fa.accountid AS Account_ID,MAX(fa.creditlimit) AS Maximum_Credit_Limit FROM l2_reporting_sch.factaccountsnapshot_final fa WHERE fa.creditlimit IS NOT NULL GROUP BY  FILTERREPORTINGPERIOD,    fa.accountid HAVING MAX(fa.creditlimit) = (SELECT   MAX(fa2.creditlimit) FROM l2_reporting_sch.factaccountsnapshot_final fa2 WHERE fa2.creditlimit IS NOT NULL) ORDER BY fa.accountid;"""

    try:
        # Run blocking authentication in a thread
        conn = await authenticate_redshift_user(
            username="ptx_nlp_user",
            password="Pass@123"
        )
        if conn is None:
            state['result'] = {}
            return state

        cursor = conn.cursor()

        # Run blocking cursor operations in a thread
        #await asyncio.to_thread(cursor.execute, "SET search_path TO l2_reporting_sch_demo;")
        await asyncio.to_thread(cursor.execute, cleaned_sql)

        rows = await asyncio.to_thread(cursor.fetchall)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        cursor.close()
        conn.close()
        # Inside your execute_sql function, after fetching rows and columns:
        # Define keywords for sensitive columns
        sensitive_keywords = ['account_id','accountid','Account ID']
        sensitive_keywords = [kw.lower() for kw in sensitive_keywords]

        masked_data = []
        for row in rows:
            masked_row = []
            for col_name, value in zip(columns, row):
                if value is not None and any(keyword in col_name.lower() for keyword in sensitive_keywords):
                    value_str = str(value)
                    masked_value = value_str[-4:].rjust(len(value_str), '*')  # Mask all but last 4
                    masked_row.append(masked_value)
                else:
                    masked_row.append(value)
            masked_data.append(masked_row)

        result = {"columns": columns, "data": masked_data}
        state['result'] = result
        return state
        # result = {"columns": columns, "data": masked_data}
        # state['result'] = result
        # return state


    except Exception as e:
        print("Cannot Execute the SQL Query:", e)
        state["sql"] = "INVALID_QUERY_FAILED_EXECUTION"
        return state
