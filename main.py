import os
import json
from urllib.parse import urlparse
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

db_engine = None
db_connection = None


def detect_database_type(database_url):
    """Detect database type from DATABASE_URL and return driver info."""
    try:
        parsed_url = urlparse(database_url)
        scheme = parsed_url.scheme.lower()

        if scheme.startswith("postgresql") or scheme.startswith("postgres"):
            return {"type": "PostgreSQL", "driver": "psycopg2", "scheme": scheme}
        elif scheme.startswith("mysql"):
            return {"type": "MySQL", "driver": "PyMySQL", "scheme": scheme}
        elif scheme.startswith("sqlite"):
            return {"type": "SQLite", "driver": "built-in", "scheme": scheme}
        else:
            return {"type": "Unknown", "driver": "unknown", "scheme": scheme}
    except Exception as e:
        return {
            "type": "Unknown",
            "driver": "unknown",
            "scheme": "unknown",
            "error": str(e),
        }


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
    import re

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
        arguments = json.loads(tool_call.function.arguments)
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


def main():
    global db_engine, db_connection

    if not os.getenv("OPENROUTER_API_KEY"):
        raise ValueError("OPENROUTER_API_KEY is not set")

    if not os.getenv("DATABASE_URL"):
        raise ValueError("DATABASE_URL is not set")

    database_url = os.getenv("DATABASE_URL")
    db_info = detect_database_type(database_url)

    print(f"{db_info['type']} detected")

    # Handle PyMySQL dialect specification for MySQL connections
    if db_info["scheme"].startswith("mysql") and "+pymysql" not in database_url:
        # If it's a mysql:// URL without dialect, add PyMySQL dialect
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)

    db_engine = create_engine(database_url)
    db_connection = db_engine.connect()
    print("\nSQL NLP Bot initialized! Ask me anything about your database.\n")
    print("Type 'quit' to exit.\n")

    tools = [
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

    while True:
        print("\nUser: ", end="")
        user_query = input().strip()

        if user_query.lower() in ["quit", "exit", "q"]:
            print("\nGoodbye!")
            break

        if not user_query:
            continue

        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are a SQL database assistant. You help users query their database using natural language.

IMPORTANT: You can ONLY execute SELECT queries. You cannot INSERT, UPDATE, DELETE, or modify data in any way.
If the user asks for data modification in any way, politely explain that you can ONLY read data, not modify it. THIS IS VERY IMPORTANT.

When a user asks a question:
1. First use the get_table_names tool to see what tables are available
2. Use the get_table_schema tool to understand the structure of relevant tables
3. Generate and execute the appropriate SELECT query using the execute_sql_query tool
4. Provide a clear, helpful response with the results

Always explain what you're doing and format the results in a readable way. If a user asks for data modification, politely explain that you can only read data, not modify it.""",
                },
                {"role": "user", "content": user_query},
            ]

            response = client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            message = response.choices[0].message

            if message.tool_calls:
                messages.append(message)

                for tool_call in message.tool_calls:
                    result = handle_tool_call(tool_call)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result),
                        }
                    )

                final_response = client.chat.completions.create(
                    model="anthropic/claude-3.5-sonnet", messages=messages
                )

                print("\n" + final_response.choices[0].message.content + "\n")
            else:
                print("\n" + message.content + "\n")

        except Exception as e:
            print(f"\nError: {str(e)}\n")

    if db_connection:
        db_connection.close()


if __name__ == "__main__":
    main()
