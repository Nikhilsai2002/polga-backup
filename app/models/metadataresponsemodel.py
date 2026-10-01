from pydantic import BaseModel
from typing import List, Dict, Optional

class ColumnInfo(BaseModel):
    column: str
    table: Optional[str]
    description: Optional[str]

class SQLParseResult(BaseModel):
    sql: str
    tables: List[str]
    columns: List[ColumnInfo]
    table_descriptions: Dict[str, Optional[str]]
