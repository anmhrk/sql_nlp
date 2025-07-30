import os
import json
from urllib.parse import urlparse
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import create_engine
import tools

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


def main():
    global db_engine, db_connection

    if not os.getenv("OPENROUTER_API_KEY"):
        raise ValueError("OPENROUTER_API_KEY is not set")

    if not os.getenv("DATABASE_URL"):
        raise ValueError("DATABASE_URL is not set")

    database_url = os.getenv("DATABASE_URL")
    db_info = detect_database_type(database_url)

    print(f"{db_info['type']} detected")
    print("Initializing database connection...")

    # Handle PyMySQL dialect specification for MySQL connections
    if db_info["scheme"].startswith("mysql") and "+pymysql" not in database_url:
        # If it's a mysql:// URL without dialect, add PyMySQL dialect
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)

    db_engine = create_engine(database_url)
    db_connection = db_engine.connect()

    # Set up database connections for tools
    tools.set_database_connections(db_engine, db_connection)

    print("\nSQL NLP Bot is ready! Ask me anything about your database.")
    print("Type 'quit' to exit.\n")

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

            # Keep making API calls until no more tool calls are needed
            while True:
                response = client.chat.completions.create(
                    model="anthropic/claude-3.5-sonnet",
                    messages=messages,
                    tools=tools.TOOLS,
                    tool_choice="auto",
                )

                message = response.choices[0].message

                if message.tool_calls:
                    # Add the assistant's message with tool calls
                    messages.append(message)

                    # Execute each tool call and add results
                    for tool_call in message.tool_calls:
                        result = tools.handle_tool_call(tool_call)

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(result),
                            }
                        )
                    # Continue the loop to make another API call
                else:
                    # No more tool calls, we have the final response
                    print("\n" + message.content + "\n")
                    break

        except Exception as e:
            print(f"\nError: {str(e)}\n")

    if db_connection:
        db_connection.close()


if __name__ == "__main__":
    main()
