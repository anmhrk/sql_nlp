import json
import re
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

db_engine = None
db_connection = None


def set_database_connections(engine, connection):
    """Set the database engine and connection for tool functions."""
    global db_engine, db_connection
    db_engine = engine
    db_connection = connection


def get_table_names():
    """Get all table names from the database."""
    try:
        inspector = inspect(db_engine)
        table_names = inspector.get_table_names()
        return {
            "success": True,
            "tables": table_names,
            "message": f"Found {len(table_names)} tables: {', '.join(table_names)}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get table names",
        }


def get_table_schema(table_name):
    """Get all columns for a specific table in the database."""
    try:
        inspector = inspect(db_engine)
        columns = inspector.get_columns(table_name)
        schema_info = []
        for col in columns:
            schema_info.append(
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                    "primary_key": col.get("primary_key", False),
                }
            )
        return {
            "success": True,
            "table": table_name,
            "columns": schema_info,
            "message": f"Schema for table '{table_name}'",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to get schema for table '{table_name}'",
        }


def execute_sql_query(sql_query):
    """Execute a SELECT SQL query and return the results"""
    try:
        if not _is_select_query(sql_query):
            return {
                "success": False,
                "error": "Only SELECT queries are allowed",
                "message": "Security restriction: Only SELECT statements are permitted",
            }

        result = db_connection.execute(text(sql_query))
        rows = result.fetchall()
        columns = list(result.keys())

        # Convert to list of dictionaries for JSON serialization
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))

        return {
            "success": True,
            "data": data,
            "row_count": len(data),
            "columns": columns,
            "message": f"Query executed successfully. Returned {len(data)} rows.",
        }

    except SQLAlchemyError as e:
        return {"success": False, "error": str(e), "message": "SQL execution failed"}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Unexpected error during SQL execution",
        }


def _is_select_query(sql_query):
    """Validate that the query is a SELECT statement only."""
    # Remove comments if any
    cleaned_query = sql_query.strip()
    cleaned_query = re.sub(r"--.*$", "", cleaned_query, flags=re.MULTILINE)
    cleaned_query = re.sub(r"/\*.*?\*/", "", cleaned_query, flags=re.DOTALL)
    cleaned_query = cleaned_query.strip()

    if not cleaned_query:
        return False

    # Check if it starts with SELECT
    if not cleaned_query.upper().startswith("SELECT"):
        return False

    forbidden_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "REPLACE",
        "MERGE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "CALL",
        "DECLARE",
        "SET",
        "USE",
        "BEGIN",
        "ATTACH",
        "DETACH",
    ]

    statements = [stmt.strip() for stmt in cleaned_query.split(";") if stmt.strip()]

    for statement in statements:
        statement_upper = statement.upper()

        if not statement_upper.startswith("SELECT"):
            return False

        for keyword in forbidden_keywords:
            if (
                f" {keyword} " in f" {statement_upper} "
                or f" {keyword}(" in f" {statement_upper} "
            ):
                return False

    return True


def handle_tool_call(tool_call):
    """Handle tool calls from the AI model."""
    function_name = tool_call.function.name

    try:
        # Handle empty or null arguments
        arguments_str = tool_call.function.arguments or "{}"
        arguments = json.loads(arguments_str)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Invalid JSON in function arguments",
            "message": "Failed to parse function arguments",
        }

    if function_name == "get_table_names":
        return get_table_names()
    elif function_name == "get_table_schema":
        table_name = arguments.get("table_name")
        if not table_name:
            return {"success": False, "error": "table_name is required"}
        return get_table_schema(table_name)
    elif function_name == "execute_sql_query":
        sql_query = arguments.get("sql_query")
        if not sql_query:
            return {"success": False, "error": "sql_query is required"}
        return execute_sql_query(sql_query)
    else:
        return {
            "success": False,
            "error": f"Unknown function: {function_name}",
            "message": "Function not implemented",
        }


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_table_names",
            "description": "Get the names of all tables in the database to understand the database structure.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_table_schema",
            "description": "Get the schema/column information for a specific table to understand its structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "The name of the table to get schema information for",
                    }
                },
                "required": ["table_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": "Execute a SQL query against the database and return the results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": "The SQL query to execute",
                    }
                },
                "required": ["sql_query"],
                "additionalProperties": False,
            },
        },
    },
]
