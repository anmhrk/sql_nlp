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

        if user_query.lower() in ["quit", "q"]:
            print("\nGoodbye!")
            break

        if not user_query:
            continue

        try:

            async def stream_response():
                tool_count = 0
                streaming_started = False

                print("🤖 Assistant is thinking...", end="", flush=True)

                async for event in agent_executor.astream_events(
                    {"input": user_query}, version="v2"
                ):
                    event_type = event.get("event")

                    if event_type == "on_tool_start":
                        tool_count += 1
                        tool_name = event.get("name", "Unknown")
                        tool_input = event.get("data", {}).get("input", "")
                        print(f"\n🔧 Tool Call #{tool_count}: {tool_name}")
                        print(f"📝 Input: {tool_input}")
                        print("⏳ Executing...")

                    elif event_type == "on_tool_end":
                        tool_output = event.get("data", {}).get("output", "")
                        print(f"✅ Result: {tool_output}")
                        print("-" * 40)

                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk", {})
                        if hasattr(chunk, "content") and chunk.content:
                            if not streaming_started:
                                streaming_started = True
                                print("\r", end="", flush=True)
                                print("🧠 Agent reasoning:")
                                print("-" * 20)
                            print(chunk.content, end="", flush=True)

                    elif event_type == "on_chain_end":
                        if event.get("name") == "AgentExecutor":
                            if streaming_started:
                                print("\n" + "-" * 40)

                            output = event.get("data", {}).get("output", "")
                            if output:
                                if isinstance(output, dict) and "output" in output:
                                    final_message = output["output"]
                                elif isinstance(output, str):
                                    final_message = output
                                else:
                                    final_message = str(output)

                                print("\n💬 Final Response:")
                                print("-" * 20)
                                print(final_message)
                                print("=" * 60)

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
