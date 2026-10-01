# from typing import List, Dict, Optional
# import pandas as pd
# from sqlglot import parse_one, exp
# from app.models.metadataresponsemodel import ColumnInfo,SQLParseResult
# from app.agents.utils import read_data_dictionary
# import asyncio
# import re
# import os
# def clean_line(text: str) -> str:
#     if not isinstance(text, str):
#         return text
#     # Replace non-breaking and zero-width spaces
#     text = text.replace('\u00A0', ' ').replace('\u200B', ' ')
#     # Collapse multiple spaces and strip edges
#     text = re.sub(r'\s+', ' ', text).strip()
#     return text
# async def extract_sql_metadata(sql_query: str) -> SQLParseResult:
#     sql_query = sql_query.strip().rstrip(";")
#     sql_query=clean_line(sql_query)
#     df = await asyncio.to_thread(read_data_dictionary)
#     file_path = os.path.join("app", "static", "L2_Description.csv")
#     tabledescdf = await asyncio.to_thread(pd.read_csv, file_path)
#     table_descriptions: Dict[str, Optional[str]] = {}
#     for _, row in tabledescdf.iterrows():
#         table_name = str(row["Table name"]).strip().lower()
#         table_desc = str(row["Table Desc"]).strip()
#         table_descriptions[table_name] = table_desc
#     schema: Dict[str, Dict[str, str]] = {}
#     for _, row in df.iterrows():
#         table = str(row["Table Name"]).strip().lower()
#         field = str(row["Field Name"]).strip().lower()
#         desc = str(row["Description"]).strip()
#         schema.setdefault(table, {})[field] = desc

#     tree = parse_one(sql_query, read="redshift")

#     tables = [t.name.lower() for t in tree.find_all(exp.Table)]
#     alias_map = {t.alias.lower(): t.name.lower() for t in tree.find_all(exp.Table) if t.alias}
#     #columns = [(c.name.lower(), c.table.lower() if c.table else None) for c in tree.find_all(exp.Column)]
#     columns = []

#     for expr in tree.selects or []:
#         if isinstance(expr, exp.Alias):
#             target = expr.this
#         else:
#             target = expr

#         if isinstance(target, exp.Column):
#             col_name = target.name.lower()
#             table_name = target.table.lower() if target.table else None
#             columns.append((col_name, table_name))

#         elif isinstance(target, exp.Func):
#             for arg in target.args.values():
#                 if isinstance(arg, exp.Column):
#                     col_name = arg.name.lower()
#                     table_name = arg.table.lower() if arg.table else None
#                     columns.append((col_name, table_name))
#     #print(columns)    
#     matched_table_descriptions = {
#     table: table_descriptions.get(table) for table in tables
#     }
#     #print(tables)
#     alias_columns = set()
#     for select_expr in tree.expressions:
#         if isinstance(select_expr, exp.Alias):
#             alias_columns.add(select_expr.alias.lower())

#     column_details = []
#     for col, tbl in columns:
#         if tbl:
#             real_table = alias_map.get(tbl, tbl)
#             desc = schema.get(real_table, {}).get(col)
#             column_details.append(ColumnInfo(column=col, table=real_table, description=desc))
#         else:
#             found_table = next((t for t in tables if col in schema.get(t, {})), None)
#             desc = schema.get(found_table, {}).get(col) if found_table else None
#             column_details.append(ColumnInfo(column=col, table=found_table, description=desc))

#     return SQLParseResult(sql=sql_query, tables=tables, columns=column_details,table_descriptions=matched_table_descriptions)


from typing import List, Dict, Optional, Tuple, Any
import pandas as pd
import asyncio
import os
import re

from sqlglot import parse_one, exp
from app.models.metadataresponsemodel import ColumnInfo, SQLParseResult
from app.agents.utils import read_data_dictionary


def clean_line(text: str) -> str:
    """
    Normalize whitespace and invisible characters in SQL strings.
    """
    if not isinstance(text, str):
        return text
    text = text.replace("\u00A0", " ").replace("\u200B", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_ident_for_lookup(name: str) -> str:
    """
    Lowercase identifier and strip surrounding double quotes if present.
    Used for robust matching of subquery aliases like "DATE".
    """
    if not isinstance(name, str):
        return name
    name = name.strip()
    if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
        name = name[1:-1]
    return name.lower()


def _get_table_identifier(t: exp.Table) -> str:
    """
    Returns a normalized base table identifier without schema, lowercase.
    E.g., l2_loans_sch.dim_customer -> dim_customer
    """
    return t.name.lower()


def _get_table_alias(t: exp.Table) -> Optional[str]:
    """
    Safely extract the table alias (lowercase) from a Table node.
    """
    a = t.args.get("alias")
    if a and isinstance(a, exp.TableAlias):
        alias_id = a.this
        if isinstance(alias_id, (exp.Identifier, exp.Column)):
            return alias_id.name.lower()
    return None


def _collect_tables_and_aliases(tree: exp.Expression) -> Tuple[List[str], Dict[str, str]]:
    """
    Walk the entire AST to collect base tables and alias mappings.
    Returns:
        tables: list of unique base table names (lowercase, no schema)
        alias_map: {alias -> base_table}
    """
    tables: List[str] = []
    alias_map: Dict[str, str] = {}

    for t in tree.find_all(exp.Table):
        name = _get_table_identifier(t)
        if name not in tables:
            tables.append(name)
        alias = _get_table_alias(t)
        if alias:
            alias_map[alias] = name

    return tables, alias_map


def _find_columns_in_expression(e: exp.Expression) -> List[Tuple[Optional[str], str]]:
    """
    Traverse any expression and extract [(table_or_alias, column)] pairs.
    table_or_alias may be None for unqualified columns.
    """
    cols: List[Tuple[Optional[str], str]] = []
    for c in e.find_all(exp.Column):
        table_part = c.table
        table_or_alias = table_part.lower() if table_part else None
        cols.append((table_or_alias, c.name.lower()))
    return cols


def _resolve_table_for_unqualified(col: str, tables: List[str], schema: Dict[str, Dict[str, str]]) -> Optional[str]:
    """
    If a column is unqualified, try to infer its table by scanning the schema map.
    Returns base table name or None.
    """
    for t in tables:
        if col in schema.get(t, {}):
            return t
    return None


def _render_sql(e: exp.Expression) -> str:
    """
    Render expression back to SQL (Redshift dialect). Preserves quoted identifiers when present.
    """
    return e.sql(dialect="redshift")


def _extract_select_items(select_node: exp.Select) -> List[exp.Expression]:
    """
    Return the list of select expressions from a SELECT node.
    """
    return list(select_node.expressions or [])


def _alias_text_preserving_quotes(alias_node: exp.TableAlias | exp.Expression) -> Optional[str]:
    """
    Given an alias node, return its textual name, preserving quotes for identifiers.
    """
    if not isinstance(alias_node, exp.TableAlias):
        return None
    ident = alias_node.this
    if isinstance(ident, exp.Identifier):
        name = ident.name
        if ident.args.get("quoted"):
            return f"\"{name}\""
        return name
    # Fallbacks (rare)
    try:
        return ident.name  # type: ignore[attr-defined]
    except Exception:
        return str(ident)


def _get_alias_or_name(expr: exp.Expression) -> str:
    """
    Determine the display name for a select expression:
      - Use alias (preserving quotes) if present
      - If bare column with no alias, return its name
      - Else return the expression SQL
    """
    if isinstance(expr, exp.Alias):
        alias_text = _alias_text_preserving_quotes(expr.args.get("alias"))
        if alias_text:
            return alias_text

    target = expr.this if isinstance(expr, exp.Alias) else expr
    if isinstance(target, exp.Column):
        return target.name
    return _render_sql(target)


def _resolve_sources_from_expression(
    e: exp.Expression,
    tables: List[str],
    alias_map: Dict[str, str],
    schema: Dict[str, Dict[str, str]],
    subquery_select_lineage: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Tuple[Optional[str], str]]:
    """
    Extract base (table, column) pairs from expression e, resolving:
      - qualified columns via alias_map
      - unqualified columns via schema or subquery lineage
    """
    subquery_select_lineage = subquery_select_lineage or {}
    resolved_sources: List[Tuple[Optional[str], str]] = []

    raw_cols = _find_columns_in_expression(e)
    for table_or_alias, col in raw_cols:
        if table_or_alias:
            # Resolve alias → base table if present
            real_table = alias_map.get(table_or_alias, table_or_alias)
            resolved_sources.append((real_table, col))
        else:
            # Unqualified column; try schema first
            real_table = _resolve_table_for_unqualified(col, tables, schema)
            if real_table:
                resolved_sources.append((real_table, col))
            else:
                # Try expand from subquery lineage (e.g., lvr_proxy, credit_proxy, "DATE", loan_status)
                inner_key = _normalize_ident_for_lookup(col)
                inner = subquery_select_lineage.get(inner_key)
                if inner and inner.get("source_columns"):
                    for (t, c) in inner["source_columns"]:
                        resolved_sources.append((t, c))
                else:
                    resolved_sources.append((None, col))

    return resolved_sources


def _build_lineage_for_select(
    select_node: exp.Select,
    tables: List[str],
    alias_map: Dict[str, str],
    schema: Dict[str, Dict[str, str]],
    subquery_select_lineage: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    For each select item, compute:
      - display_name: visible column name (alias or derived)
      - expression_sql: SQL of the value expression (without AS name)
      - source_columns: list of (table, column) pairs feeding the expression,
                        expanding through subquery aliases where possible
      - simple_table: if it is a bare column, the base table; else None
    """
    results: List[Dict[str, Any]] = []
    subquery_select_lineage = subquery_select_lineage or {}

    for sel_expr in _extract_select_items(select_node):
        display_name = _get_alias_or_name(sel_expr)
        payload = sel_expr.this if isinstance(sel_expr, exp.Alias) else sel_expr

        resolved_sources = _resolve_sources_from_expression(
            payload, tables, alias_map, schema, subquery_select_lineage=subquery_select_lineage
        )

        simple_table = None
        if isinstance(payload, exp.Column):
            if resolved_sources:
                simple_table = resolved_sources[0][0]

        results.append({
            "display_name": display_name,
            "expression_sql": _render_sql(payload),
            "source_columns": resolved_sources,   # list[(table, column)]
            "simple_table": simple_table
        })

    return results


def _map_group_by_ordinals(select_node: exp.Select) -> Dict[int, str]:
    """
    Map GROUP BY ordinals (1-based) to the select item display names.
    Not currently returned; keep for debugging/extension.
    """
    group = select_node.args.get("group")
    if not group:
        return {}
    ordinals: List[int] = []
    for gexpr in group.expressions:
        if isinstance(gexpr, exp.Literal) and gexpr.is_int:
            ordinals.append(int(gexpr.this))

    names: List[str] = []
    for sel_expr in _extract_select_items(select_node):
        names.append(_get_alias_or_name(sel_expr))

    mapping: Dict[int, str] = {}
    for o in ordinals:
        if 1 <= o <= len(names):
            mapping[o] = names[o - 1]
    return mapping


def _collect_subquery_select_lineage(
    tree: exp.Expression,
    schema: Dict[str, Dict[str, str]],
) -> Dict[str, Dict[str, Any]]:
    """
    Build lineage map for all subqueries used as FROM sources:
      { normalized_alias (display_name) -> lineage_row }
    """
    lineage: Dict[str, Dict[str, Any]] = {}

    # We still need alias_map & tables local to each subquery when building its lineage
    for sub in tree.find_all(exp.Subquery):
        alias_node = sub.args.get("alias")
        sub_alias = None
        if isinstance(alias_node, exp.TableAlias):
            ident = alias_node.this
            if isinstance(ident, exp.Identifier):
                sub_alias = ident.name.lower()
            elif hasattr(ident, "name"):
                sub_alias = getattr(ident, "name", None)
                sub_alias = sub_alias.lower() if sub_alias else None

        sub_select = sub.this if isinstance(sub.this, exp.Select) else None

        if sub_select is not None:
            sub_tables, sub_alias_map = _collect_tables_and_aliases(sub_select)
            sub_lineage_rows = _build_lineage_for_select(
                sub_select, sub_tables, sub_alias_map, schema, subquery_select_lineage=None
            )
            # Map inner select aliases (display names) for lookup
            for row in sub_lineage_rows:
                key = _normalize_ident_for_lookup(row["display_name"])
                lineage[key] = row

    return lineage


def _collect_non_select_base_sources(
    tree: exp.Expression,
    tables: List[str],
    alias_map: Dict[str, str],
    schema: Dict[str, Dict[str, str]],
    subquery_select_lineage: Dict[str, Dict[str, Any]],
) -> List[Tuple[Optional[str], str]]:
    """
    Optionally collect base columns used in JOIN ON, WHERE, and ORDER BY clauses
    across the entire query AST.
    """
    sources: List[Tuple[Optional[str], str]] = []

    # JOIN conditions
    for j in tree.find_all(exp.Join):
        on_expr = j.args.get("on")
        if on_expr:
            sources.extend(_resolve_sources_from_expression(
                on_expr, tables, alias_map, schema, subquery_select_lineage
            ))

    # WHERE clauses
    for w in tree.find_all(exp.Where):
        if w.this:
            sources.extend(_resolve_sources_from_expression(
                w.this, tables, alias_map, schema, subquery_select_lineage
            ))

    # ORDER BY (can reference select aliases or base cols)
    for sel in tree.find_all(exp.Select):
        order = sel.args.get("order")
        if order:
            for oexpr in order.expressions or []:
                sources.extend(_resolve_sources_from_expression(
                    oexpr, tables, alias_map, schema, subquery_select_lineage
                ))

    # GROUP BY direct expressions (not ordinals)
    for sel in tree.find_all(exp.Select):
        group = sel.args.get("group")
        if group:
            for gexpr in group.expressions or []:
                # If it's an integer literal (ordinal), skip—handled via select lineage
                if isinstance(gexpr, exp.Literal) and gexpr.is_int:
                    continue
                sources.extend(_resolve_sources_from_expression(
                    gexpr, tables, alias_map, schema, subquery_select_lineage
                ))

    return sources


async def extract_sql_metadata(
    sql_query: str,
    *,
    include_non_select_sources: bool = False
) -> SQLParseResult:
    """
    Parse a Redshift SQL query and return:
      - base tables (no schema)
      - columns: ONLY underlying base columns (table, column, description),
                 de-duplicated, derived from select expressions
                 (optionally includes JOIN/WHERE/ORDER BY columns)
      - table descriptions

    Enhancements:
      - Resolves derived columns from subqueries (aliases)
      - Traverses expressions (CASE, functions, arithmetic, concat)
      - Preserves quoted identifiers for internal display logic
      - Maps GROUP BY ordinals internally (not returned)
      - Robustly resolves unqualified columns via schema or subquery lineage
    """
    sql_query = clean_line(sql_query.strip().rstrip(";"))

    # Load your data dictionary and table descriptions
    df = await asyncio.to_thread(read_data_dictionary)
    file_path = os.path.join("app", "static", "L2_Description.csv")
    tabledescdf = await asyncio.to_thread(pd.read_csv, file_path)

    table_descriptions: Dict[str, Optional[str]] = {}
    for _, row in tabledescdf.iterrows():
        table_name = str(row["Table name"]).strip().lower()
        table_desc = str(row["Table Desc"]).strip()
        table_descriptions[table_name] = table_desc

    # Build schema map: {table: {column: description}}
    schema: Dict[str, Dict[str, str]] = {}
    for _, row in df.iterrows():
        table = str(row["Table Name"]).strip().lower()
        field = str(row["Field Name"]).strip().lower()
        desc = str(row["Description"]).strip()
        schema.setdefault(table, {})[field] = desc

    # Parse with Redshift dialect
    tree = parse_one(sql_query, read="redshift")

    # Ensure we pick the OUTERMOST SELECT (last one in traversal)
    selects = list(tree.find_all(exp.Select))
    outer_select = selects[-1] if selects else None
    if outer_select is None:
        # Fallback: no SELECT found; return minimal info
        return SQLParseResult(
            sql=sql_query,
            tables=[],
            columns=[],
            table_descriptions={}
        )

    # Collect all base tables and alias map across the query
    tables, alias_map = _collect_tables_and_aliases(tree)

    # Build subquery lineage for FROM (...) subqueries (for resolving outer refs like lvr_proxy)
    subquery_select_lineage = _collect_subquery_select_lineage(tree, schema)

    # Build lineage for the OUTER SELECT, with access to inner (subquery) lineage
    outer_lineage = _build_lineage_for_select(
        outer_select, tables, alias_map, schema, subquery_select_lineage=subquery_select_lineage
    )

    # Optional: Map GROUP BY ordinals (not returned; helpful for debugging/extension)
    # group_by_map = _map_group_by_ordinals(outer_select)

    # ---- Assemble ONLY base (table, column) pairs ----
    base_sources: List[Tuple[Optional[str], str]] = []
    for row in outer_lineage:
        for (t, c) in row["source_columns"]:
            if t and c:
                base_sources.append((t, c))

    # Optionally include JOIN / WHERE / ORDER BY base columns
    if include_non_select_sources:
        extra_sources = _collect_non_select_base_sources(
            tree, tables, alias_map, schema, subquery_select_lineage
        )
        for (t, c) in extra_sources:
            if t and c:
                base_sources.append((t, c))

    # Deduplicate while preserving order
    seen = set()
    unique_base_sources: List[Tuple[str, str]] = []
    for t, c in base_sources:
        key = (t, c)
        if key not in seen:
            seen.add(key)
            unique_base_sources.append((t, c))

    # Build ColumnInfo only for base columns
    column_details: List[ColumnInfo] = []
    for t, c in unique_base_sources:
        desc = schema.get(t, {}).get(c)
        column_details.append(
            ColumnInfo(
                column=c,          # real column name (lowercase)
                table=t,           # base table (lowercase)
                description=desc
            )
        )

    matched_table_descriptions = {t: table_descriptions.get(t) for t in tables}

    return SQLParseResult(
        sql=sql_query,
        tables=tables,
        columns=column_details,
        table_descriptions=matched_table_descriptions
    )






# from typing import List, Dict, Optional, Tuple, Set
# import pandas as pd
# from sqlglot import parse_one, exp
# from app.models.metadataresponsemodel import ColumnInfo, SQLParseResult
# from app.agents.utils import read_data_dictionary
# import asyncio
# import re
# import os


# # ---------------------------
# # Utilities & Loaders
# # ---------------------------

# def clean_line(text: str) -> str:
#     """Normalize whitespace and invisible characters."""
#     if not isinstance(text, str):
#         return text
#     text = text.replace("\u00A0", " ").replace("\u200B", " ")
#     text = re.sub(r"\s+", " ", text).strip()
#     return text

# def _lower(s: Optional[str]) -> Optional[str]:
#     return s.lower() if isinstance(s, str) else s

# def _identifier_name(node: Optional[exp.Expression]) -> Optional[str]:
#     """
#     Extract the plain string name from an Identifier-like node: exp.Identifier, Literal, or str.
#     Returns lowercased name or None.
#     """
#     if node is None:
#         return None
#     if isinstance(node, str):
#         return node.strip('"').strip().lower()
#     if isinstance(node, exp.Identifier):
#         return (node.this or "").strip('"').strip().lower()
#     if isinstance(node, exp.Literal):
#         return (node.this or "").strip('"').strip().lower()
#     # Fallback: best-effort string
#     return str(node).strip('"').strip().lower()

# def _table_alias_name(t: exp.Table) -> Optional[str]:
#     """
#     Get alias name (lowercased) for a Table node, regardless of whether alias is a string or exp.TableAlias.
#     """
#     # sqlglot usually stores alias in t.args['alias'] as an exp.TableAlias
#     a = t.args.get("alias")
#     if isinstance(a, exp.TableAlias):
#         return _identifier_name(a.this)
#     # Some versions expose t.alias as exp.TableAlias or str
#     if isinstance(getattr(t, "alias", None), exp.TableAlias):
#         return _identifier_name(t.alias.this)
#     if isinstance(getattr(t, "alias", None), str):
#         return _identifier_name(t.alias)
#     return None

# def _table_base_name(t: exp.Table) -> Optional[str]:
#     """
#     Return the physical table name (object name only, without schema/catalog), lowercased.
#     """
#     # t.name is the base object name in sqlglot (without db/schema)
#     return _identifier_name(t.name)

# def _build_alias_to_base_map(tree: exp.Expression) -> Dict[str, str]:
#     """
#     Build a global alias->base_table map across all Table nodes (CTEs + outer query scopes).
#     This prevents scope aliases (dc, fa, dd, db, fr, ...) from leaking into final output.
#     """
#     m: Dict[str, str] = {}
#     for t in tree.find_all(exp.Table):
#         alias = _table_alias_name(t)
#         base = _table_base_name(t)
#         if alias and base:
#             m[alias] = base
#     return m

# def _collect_table_aliases(select_node: exp.Select) -> Dict[str, str]:
#     """
#     Build a map of alias -> base table name for the current SELECT scope (FROM/JOIN only).
#     """
#     alias_map: Dict[str, str] = {}
#     from_clause = select_node.args.get("from")
#     if not from_clause:
#         return alias_map

#     for t in from_clause.find_all(exp.Table):
#         tname = _table_base_name(t)     # base table name (no schema)
#         talias = _table_alias_name(t)   # alias in this scope
#         if tname and talias:
#             alias_map[talias] = tname
#     return alias_map

# def _select_sources(select_node: exp.Select) -> Tuple[List[str], Dict[str, str]]:
#     """
#     Return:
#       - list of 'source keys' for FROM/JOIN: alias if present, else table name (lowercased)
#       - map source_key -> underlying base table name (lowercased)
#     """
#     sources: List[str] = []
#     key_to_underlying: Dict[str, str] = {}
#     from_clause = select_node.args.get("from")
#     if not from_clause:
#         return sources, key_to_underlying

#     for t in from_clause.find_all(exp.Table):
#         raw = _table_alias_name(t) or _table_base_name(t)
#         underlying = _table_base_name(t)
#         if raw:
#             sources.append(raw)
#             key_to_underlying[raw] = underlying
#     return sources, key_to_underlying

# def _columns_in_expr(e: exp.Expression) -> List[Tuple[str, Optional[str]]]:
#     """
#     Return a list of (column_name, qualifier_or_None) for all Column nodes under expression e.
#     Qualifier is the table/alias/cte if present, else None.
#     """
#     cols: List[Tuple[str, Optional[str]]] = []
#     for c in e.find_all(exp.Column):
#         cname = _identifier_name(c.args.get("this")) or _lower(getattr(c, "name", None))
#         ctbl = _identifier_name(c.args.get("table")) if c.args.get("table") else None
#         # Fallbacks
#         if cname is None:
#             cname = _lower(getattr(c, "name", None))
#         if ctbl is None and getattr(c, "table", None):
#             ctbl = _lower(getattr(c, "table", None))
#         cols.append((cname, ctbl))
#     return cols

# def _cte_outputs(
#     select_node: exp.Select,
#     schema: Dict[str, Dict[str, str]],
#     alias_to_base: Dict[str, str],
# ) -> Dict[str, List[Tuple[str, Optional[str]]]]:
#     """
#     For a CTE SELECT, return a mapping:
#       visible_column_name_in_cte -> list of (base_column_name, resolved_base_table) sources.
#     Ensures tables are normalized to base physical names (no aliases).
#     """
#     outputs: Dict[str, List[Tuple[str, Optional[str]]]] = {}
#     local_alias_map = _collect_table_aliases(select_node)

#     def _normalize_tbl(tbl: Optional[str]) -> Optional[str]:
#         if tbl is None:
#             return None
#         # prefer local alias map first, then global alias_to_base
#         return local_alias_map.get(tbl) or alias_to_base.get(tbl) or tbl

#     for proj in select_node.expressions or []:
#         if isinstance(proj, exp.Alias):
#             visible_name = _identifier_name(proj.alias) or _identifier_name(proj.args.get("alias"))
#             target = proj.this
#         else:
#             target = proj
#             if isinstance(target, exp.Column):
#                 visible_name = _identifier_name(target.args.get("this")) or _lower(getattr(target, "name", None))
#             else:
#                 visible_name = _lower(target.sql())

#         nested_cols = _columns_in_expr(target)
#         resolved_sources: List[Tuple[str, Optional[str]]] = []
#         for col, tbl in nested_cols:
#             resolved_tbl = _normalize_tbl(tbl)

#             # If still None, try heuristic across base tables in this CTE scope
#             if resolved_tbl is None and schema and local_alias_map:
#                 candidates = set(local_alias_map.values())
#                 found = next((t for t in candidates if col in schema.get(t, {})), None)
#                 resolved_tbl = found

#             resolved_sources.append((col, resolved_tbl))

#         outputs.setdefault(visible_name, resolved_sources)

#     return outputs

# def _resolve_unqualified_pairs(
#     pairs: List[Tuple[str, Optional[str]]],
#     tables_in_query: List[str],
#     schema: Dict[str, Dict[str, str]],
# ) -> List[Tuple[str, Optional[str]]]:
#     """
#     For (col, None) pairs, try to uniquely resolve to a base table among the query's base tables.
#     If ambiguous or absent, keep table as None.
#     """
#     out: List[Tuple[str, Optional[str]]] = []
#     for col, tbl in pairs:
#         if tbl is None:
#             candidates = [t for t in tables_in_query if col in schema.get(t, {})]
#             if len(candidates) == 1:
#                 out.append((col, candidates[0]))
#             else:
#                 out.append((col, None))
#         else:
#             out.append((col, tbl))
#     return out

# def _add_base_columns_only(
#     collected: List[Tuple[str, Optional[str]]],
#     schema: Dict[str, Dict[str, str]],
#     dedup_set: set,
#     out_columns: List[ColumnInfo],
# ):
#     """
#     Emit ColumnInfo for base (table, col) pairs only (no projection aliases).
#     Deduplicates by (table, col).
#     """
#     for scol, stbl in collected:
#         key = ((stbl or ""), (scol or ""))
#         if key in dedup_set:
#             continue
#         dedup_set.add(key)
#         desc = schema.get(stbl, {}).get(scol) if stbl else None
#         out_columns.append(ColumnInfo(column=scol, table=stbl, description=desc))

# def _load_table_descriptions(path: str) -> Dict[str, Optional[str]]:
#     """
#     Robust loader for L2_Description:
#       - supports headered or headerless CSV
#       - case-insensitive header names when present
#     Expected columns when headerless: [index, table_name, table_desc]
#     """
#     try:
#         df = pd.read_csv(path)
#         cols = {c.lower(): c for c in df.columns}
#         tcol = cols.get("table name") or cols.get("table") or cols.get("table_name") or cols.get("tablename")
#         dcol = cols.get("table desc") or cols.get("description") or cols.get("table_description") or cols.get("desc")
#         if not tcol or not dcol:
#             raise ValueError("Missing expected headers")
#     except Exception:
#         df = pd.read_csv(path, header=None, names=["idx", "table_name", "table_desc"])
#         tcol = "table_name"
#         dcol = "table_desc"

#     out: Dict[str, Optional[str]] = {}
#     for _, row in df.iterrows():
#         table_name = str(row[tcol]).strip().lower()
#         table_desc = str(row[dcol]).strip()
#         out[table_name] = table_desc
#     return out


# # ---------------------------
# # Main API
# # ---------------------------

# async def extract_sql_metadata(sql_query: str) -> SQLParseResult:
#     """
#     Parse SQL (Redshift dialect) and return:
#       - tables: list of base tables used (excluding CTE names)
#       - columns: ONLY the base columns that contribute to the final SELECT projections (no projection aliases; no table aliases)
#       - table_descriptions: map of base tables -> description from L2_Description.csv
#       - sql: cleaned SQL text
#     Notes:
#       * CTEs are resolved to their base lineage.
#       * Columns are deduplicated (table, column).
#       * Unqualified columns are resolved heuristically among tables in the query when unique.
#       * A global alias->base map across all scopes prevents alias leakage.
#     """
#     sql_query = clean_line(sql_query.strip().rstrip(";"))

#     # Load data dictionary (columns) — expected columns: "Table Name", "Field Name", "Description"
#     df = await asyncio.to_thread(read_data_dictionary)

#     # Load table descriptions (robustly)
#     file_path = os.path.join("app", "static", "L2_Description.csv")
#     table_descriptions = await asyncio.to_thread(_load_table_descriptions, file_path)

#     # Build schema: table -> column -> description (lower-cased)
#     schema: Dict[str, Dict[str, str]] = {}
#     for _, row in df.iterrows():
#         table = str(row["Table Name"]).strip().lower()
#         field = str(row["Field Name"]).strip().lower()
#         desc = str(row["Description"]).strip()
#         schema.setdefault(table, {})[field] = desc

#     # Parse
#     tree = parse_one(sql_query, read="redshift")

#     # Build a global alias->base map across every Table node (CTEs + outer)
#     alias_to_base = _build_alias_to_base_map(tree)

#     # --- Identify CTEs (WITH clause) ---
#     with_clause = tree.args.get("with")
#     cte_names: Set[str] = set()
#     cte_maps: Dict[str, Dict[str, List[Tuple[str, Optional[str]]]]] = {}

#     if isinstance(with_clause, exp.With):
#         for cte in with_clause.expressions or []:
#             cte_alias_name = _identifier_name(getattr(cte, "alias", None)) or _identifier_name(cte.args.get("alias"))
#             if not cte_alias_name:
#                 continue
#             cte_names.add(cte_alias_name)
#             sub = cte.this
#             # unwrap Subquery if present
#             cte_select = sub.this if isinstance(sub, exp.Subquery) else sub
#             if isinstance(cte_select, exp.Select):
#                 cte_maps[cte_alias_name] = _cte_outputs(cte_select, schema, alias_to_base)
#             else:
#                 cte_maps[cte_alias_name] = {}

#     # --- Gather real base tables (exclude CTE names) ---
#     all_tables: List[str] = []
#     for t in tree.find_all(exp.Table):
#         tname = _table_base_name(t)
#         if tname and tname not in cte_names:
#             all_tables.append(tname)
#     # unique preserving order
#     seen = set()
#     tables: List[str] = [t for t in all_tables if not (t in seen or seen.add(t))]

#     # Matched table descriptions for base tables only
#     matched_table_descriptions = {t: table_descriptions.get(t) for t in tables}

#     # --- Resolve final SELECT (projection-only) to base columns ---
#     column_details: List[ColumnInfo] = []

#     # Find the outermost SELECT
#     outer_select = tree
#     if not isinstance(outer_select, exp.Select):
#         outer_select = tree.find(exp.Select) or tree

#     if isinstance(outer_select, exp.Select):
#         alias_map_outer = _collect_table_aliases(outer_select)
#         from_sources, source_to_underlying = _select_sources(outer_select)

#         # We'll collect deduped base sources here
#         dedup_sources = set()

#         for proj in outer_select.expressions or []:
#             target = proj.this if isinstance(proj, exp.Alias) else proj
#             nested_cols = _columns_in_expr(target)

#             resolved_pairs: List[Tuple[str, Optional[str]]] = []
#             for col, tbl in nested_cols:
#                 # Step 1: normalize qualifier via outer alias map, then global alias_to_base
#                 real_tbl = alias_map_outer.get(tbl, tbl)
#                 real_tbl = alias_to_base.get(real_tbl, real_tbl) if real_tbl is not None else None

#                 # Step 2: if unqualified in the outer query, try resolving through CTE sources first
#                 if real_tbl is None:
#                     # If there is exactly one FROM source and it's a CTE, map through that CTE
#                     if len(from_sources) == 1:
#                         only_src = from_sources[0]
#                         underlying = source_to_underlying.get(only_src, only_src)
#                         if underlying in cte_names or only_src in cte_names:
#                             sources = cte_maps.get(underlying, {}) or cte_maps.get(only_src, {})
#                             lineage = sources.get(col, [])
#                             if lineage:
#                                 # lineage contains (base_col, base_table) but ensure base_table is normalized
#                                 lineage = [(c, alias_to_base.get(t, t) if t else None) for c, t in lineage]
#                                 resolved_pairs.extend(lineage)
#                                 continue
#                             else:
#                                 resolved_pairs.append((col, None))
#                                 continue

#                     # If multiple sources, try each CTE source for a match
#                     any_cte_resolved = False
#                     for src_key in from_sources:
#                         underlying = source_to_underlying.get(src_key, src_key)
#                         if underlying in cte_names or src_key in cte_names:
#                             sources = cte_maps.get(underlying, {}) or cte_maps.get(src_key, {})
#                             lineage = sources.get(col, [])
#                             if lineage:
#                                 lineage = [(c, alias_to_base.get(t, t) if t else None) for c, t in lineage]
#                                 resolved_pairs.extend(lineage)
#                                 any_cte_resolved = True
#                                 break
#                     if any_cte_resolved:
#                         continue

#                     # Otherwise, keep as unqualified and attempt heuristic later
#                     resolved_pairs.append((col, None))
#                     continue

#                 # Step 3: if qualified and that qualifier is a CTE, map through CTE lineage
#                 if real_tbl in cte_names:
#                     sources = cte_maps.get(real_tbl, {})
#                     lineage = sources.get(col, [])
#                     if lineage:
#                         lineage = [(c, alias_to_base.get(t, t) if t else None) for c, t in lineage]
#                         resolved_pairs.extend(lineage)
#                     else:
#                         resolved_pairs.append((col, None))
#                 else:
#                     # Step 4: qualified to a base table alias or table — real_tbl already normalized
#                     resolved_pairs.append((col, real_tbl))

#             # Step 5: heuristically resolve any remaining unqualified pairs among base tables in this query
#             resolved_pairs = _resolve_unqualified_pairs(resolved_pairs, tables, schema)

#             # Step 6: emit base columns only (deduped) with descriptions
#             _add_base_columns_only(resolved_pairs, schema, dedup_sources, column_details)

#     return SQLParseResult(
#         sql=sql_query,
#         tables=tables,
#         columns=column_details,
#         table_descriptions=matched_table_descriptions,
#     )