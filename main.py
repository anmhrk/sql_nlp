import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from agent import create_agent

load_dotenv()

db_engine = None
db_connection = None


def main():
    global db_engine, db_connection

    if not os.getenv("OPENROUTER_API_KEY"):
        raise ValueError("OPENROUTER_API_KEY is not set")

    if not os.getenv("DATABASE_URL"):
        raise ValueError("DATABASE_URL is not set")

    database_url = os.getenv("DATABASE_URL")
    print("Initializing database connection...")

    try:
        db_engine = create_engine(database_url)
        db_connection = db_engine.connect()
        print("✅ Database connection established successfully!")

        agent_executor = create_agent(db_engine, db_connection)
    except SQLAlchemyError as e:
        print(f"❌ Failed to connect to database: {e}")
        print("\n💡 Please check:")
        print("- DATABASE_URL is correct and accessible")
        print("- Database server is running")
        print("- Credentials are valid")
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

        print("\n" + "=" * 60)
        print("🤖 Assistant is thinking...")
        print("=" * 60)

        # Stream the response
        final_output = ""
        tool_count = 0

        try:
            for chunk in agent_executor.stream({"input": user_query}):
                # Handle different types of chunks
                if "actions" in chunk:
                    # Tool calls
                    for action in chunk["actions"]:
                        tool_count += 1
                        print(f"\n🔧 Tool Call #{tool_count}: {action.tool}")
                        print(f"📝 Input: {action.tool_input}")
                        print("⏳ Executing...")

                elif "steps" in chunk:
                    # Tool results
                    for step in chunk["steps"]:
                        result = step.observation
                        print(f"✅ Result: {result}")
                        print("-" * 40)

                elif "output" in chunk:
                    # Final output
                    output_text = chunk["output"]
                    final_output = output_text
                    print("\n💬 Final Response:")
                    print("-" * 20)
                    print(output_text)
                    print("=" * 60)

            if not final_output:
                print("❌ No response generated.")

        except SQLAlchemyError as e:
            print(f"❌ Database Error: {e}")
            print("\n💡 Suggestions:")
            print("- Check if your database is running and accessible")
            print("- Verify your DATABASE_URL environment variable")
            print("- Ensure you have proper database permissions")
            print("=" * 60)
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            print("\n💡 If this persists, please check your configuration.")
            print("=" * 60)

    if db_connection:
        db_connection.close()


if __name__ == "__main__":
    main()
