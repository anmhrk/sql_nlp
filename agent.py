import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from pydantic import SecretStr
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

model = "anthropic/claude-sonnet-4"

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a helpful SQL database assistant. You help users answer questions about their database by querying their database.

CRITICAL RULES:
1. You can ONLY execute SELECT queries. No INSERT, UPDATE, DELETE, or data modification allowed even if the user asks. This is a very STRICT rule.
2. Column names are CASE-SENSITIVE. Always use the EXACT column names from the schema.
3. When you get a schema, pay close attention to the exact spelling and case of column names.
4. Use double quotes around column names if they contain special characters or mixed case.

WORKFLOW:
1. First, get table names to understand the database structure
2. Then, get the schema for relevant tables to see exact column names and types
3. Finally, write your SQL query using the EXACT column names from the schema

SQL BEST PRACTICES:
- Always use the exact column names shown in the schema output
- Pay attention to case sensitivity (e.g., "createdAt" vs "createdat")
- Use double quotes around column/table names when needed: SELECT "createdAt" FROM "messages"
- If a query fails due to column names, check the schema again for exact spelling

You have access to these tools:
- get_table_names: Get all table names in the database
- get_table_schema: Get detailed column information for a specific table (shows exact column names)
- execute_sql_query: Execute a SELECT query (only SELECT queries allowed)

Always use the schema information to write accurate SQL queries with correct column names.
""",
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)


def create_agent(db_engine, db_connection):
    """Create an agent with database tools."""

    OPENROUTER_API_KEY = SecretStr(os.getenv("OPENROUTER_API_KEY"))
    llm = ChatOpenAI(
        model=model,
        temperature=0.0,
        streaming=True,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

    @tool
    def get_table_names() -> str:
        """Get the names of all tables in the database to understand the database structure."""
        try:
            inspector = inspect(db_engine)
            table_names = inspector.get_table_names()

            if not table_names:
                return "No tables found in the database."

            result = f"Found {len(table_names)} tables in the database:\n"
            for i, table in enumerate(table_names, 1):
                result += f"{i}. {table}\n"

            return result.strip()
        except SQLAlchemyError as e:
            return f"Database error while getting table names: {str(e)}"
        except Exception as e:
            return f"Unexpected error while getting table names: {str(e)}"

    @tool
    def get_table_schema(table_name: str) -> str:
        """Get the schema/column information for a specific table to understand its structure."""
        try:
            inspector = inspect(db_engine)
            columns = inspector.get_columns(table_name)

            if not columns:
                return f"No columns found for table '{table_name}' or table does not exist."

            result = f"Schema for table '{table_name}':\n"
            result += "=" * 50 + "\n"
            result += f"Total columns: {len(columns)}\n\n"

            for i, col in enumerate(columns, 1):
                col_name = col["name"]
                col_type = str(col["type"])
                nullable = "NULL" if col["nullable"] else "NOT NULL"
                primary_key = " (PRIMARY KEY)" if col.get("primary_key", False) else ""

                result += f"{i:2}. Column: '{col_name}'\n"
                result += f"    Type: {col_type}\n"
                result += f"    Constraints: {nullable}{primary_key}\n\n"

            return result
        except SQLAlchemyError as e:
            return f"Database error while getting schema for table '{table_name}': {str(e)}"
        except Exception as e:
            return f"Unexpected error while getting schema for table '{table_name}': {str(e)}"

    @tool
    def execute_sql_query(sql_query: str) -> str:
        """Execute a SQL query and return the results. ONLY SELECT queries are allowed."""
        query_upper = sql_query.strip().upper()
        if not query_upper.startswith("SELECT"):
            return "ERROR: Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, or other modification queries."

        try:
            result = db_connection.execute(text(sql_query))
            rows = result.fetchall()
            columns = list(result.keys())

            if not rows:
                return f"Query executed successfully but returned no results.\nQuery: {sql_query}"

            output = f"Query Results ({len(rows)} row(s)):\n"
            output += "=" * 50 + "\n"
            output += f"SQL: {sql_query}\n\n"

            output += "Columns: " + " | ".join(columns) + "\n"
            output += "-" * 50 + "\n"

            for i, row in enumerate(rows, 1):
                output += f"Row {i}:\n"
                for col, value in zip(columns, row):
                    output += f"  {col}: {value}\n"
                output += "\n"

            output += (
                f"Summary: {len(rows)} row(s) returned with {len(columns)} column(s)"
            )

            return output

        except SQLAlchemyError as e:
            error_msg = str(e)
            if "column" in error_msg.lower() and "does not exist" in error_msg.lower():
                return f"SQL ERROR - Column does not exist: {error_msg}\n\nHINT: Check column names for exact case sensitivity. Use double quotes around column names if needed.\nQuery attempted: {sql_query}"
            elif "table" in error_msg.lower() and "does not exist" in error_msg.lower():
                return f"SQL ERROR - Table does not exist: {error_msg}\n\nHINT: Use get_table_names to see available tables.\nQuery attempted: {sql_query}"
            else:
                return f"SQL ERROR: {error_msg}\nQuery attempted: {sql_query}"
        except Exception as e:
            return f"Unexpected error executing query: {str(e)}\nQuery attempted: {sql_query}"

    tools = [get_table_names, get_table_schema, execute_sql_query]

    agent = create_tool_calling_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        stream_runnable=True,
        return_intermediate_steps=True,
    )

    return agent_executor
