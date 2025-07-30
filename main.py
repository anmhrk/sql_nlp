import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from agent import create_agent
from getpass import getpass
import asyncio

load_dotenv()  # In case of using .env file

db_engine = None
db_connection = None


def main():
    global db_engine, db_connection

    if not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = getpass(
            "Please enter your OpenRouter API key: "
        )

    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = getpass("Please enter your database URL: ")

    database_url = os.environ.get("DATABASE_URL")

    if "mysql" in database_url:
        database_url = database_url.replace("mysql", "mysql+pymysql")

    print("Initializing database connection...")

    try:
        db_engine = create_engine(database_url)
        db_connection = db_engine.connect()
        print("✅ Database connection established successfully!")

        agent_executor = create_agent(db_engine, db_connection)
    except SQLAlchemyError as e:
        print(f"❌ Failed to connect to database: {e}")
        return
    except Exception as e:
        print(f"❌ Unexpected error during setup: {e}")
        return

    print("\nSQL NLP Bot is ready! Ask me anything about your database.")
    print("Type 'quit' or 'q' to exit.\n")

    while True:
        print("\nUser: ", end="")
        user_query = input().strip()
        print("\n")

        if user_query.lower() in ["quit", "q"]:
            print("Goodbye!")
            break

        if not user_query:
            continue

        print("🤖 The bot is thinking...\n")

        try:

            async def stream_response():
                tool_count = 0

                async for event in agent_executor.astream_events(
                    {"input": user_query}, version="v2"
                ):
                    event_type = event.get("event")

                    if event_type == "on_tool_start":
                        tool_count += 1
                        tool_name = event.get("name", "Unknown")
                        tool_input = event.get("data", {}).get("input", "")
                        print(f"\n🔧 **Tool #{tool_count}: {tool_name}**")
                        print(f"   Input: {tool_input}")
                        print("   Status: Executing...", end="", flush=True)

                    elif event_type == "on_tool_end":
                        tool_output = event.get("data", {}).get("output", "")
                        print("\r   Status: ✅ Complete")
                        print(f"   Result: {tool_output}")
                        print("   " + "─" * 50)
                        print("\n")

                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk", {})
                        if hasattr(chunk, "content") and chunk.content:
                            print(chunk.content, end="", flush=True)

            asyncio.run(stream_response())

        except SQLAlchemyError as e:
            print(f"❌ Database Error: {e}")
            print("=" * 60)
        except KeyboardInterrupt:
            print("\n\n❌ Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            print("=" * 60)

    if db_connection:
        db_connection.close()


if __name__ == "__main__":
    main()
