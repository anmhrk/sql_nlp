# SQL NLP

A Python application that allows you to interact with your SQL databases using natural language queries. Built using LangChain, OpenRouter, and SQLAlchemy.

## Configured tools for the agent:

1. get_table_names: List all tables in the database
2. get_table_schema: Get the schema of a specific table
3. execute_sql_query: Execute a custom SELECT SQL query

The agent can only read data from the database using SELECT operations. There are guardrails in place to prevent any destructive operations like INSERT, UPDATE, DELETE. The agent will refuse to execute such queries.

## Get Started

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/). It's a fast Python package and project manager alternative to pip and poetry.

2. Clone the repo:

   ```bash
   git clone <repo_url>
   cd sql_nlp
   ```

3. Run `uv sync` to install dependencies

4. (optional) Create a `.env` file in the root directory and add the following environment variables:

   - `OPENROUTER_API_KEY`: Your OpenRouter API key
   - `DATABASE_URL`: Connection string to your database (Postgres, MySQL, Sqlite)

5. If you want to create a test Postgres database, run the following commands:

   ```bash
   docker compose up -d # This will start a postgres db on port 5432
   uv run seed_test_db.py # This will seed the test database with sample data
   ```

6. The app is configured to use Claude Sonnet 4 as the LLM but you can change it in `agent.py` to an OpenAI API compatible model.

7. Run the application with `uv run main.py`

8. If you didn't create a `.env` file, it will prompt you to enter your OpenRouter API key and Database URL.

9. Start talking to your database!
