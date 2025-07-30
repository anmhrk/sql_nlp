import psycopg2
import random
from datetime import datetime, timedelta


def connect_to_db():
    return psycopg2.connect(
        host="localhost", database="testdb", user="user", password="password"
    )


def populate_data():
    conn = connect_to_db()
    cur = conn.cursor()

    users = [
        ("alice_smith", "alice@example.com"),
        ("bob_jones", "bob@example.com"),
        ("charlie_brown", "charlie@example.com"),
        ("diana_wilson", "diana@example.com"),
        ("eve_davis", "eve@example.com"),
    ]

    for username, email in users:
        cur.execute(
            "INSERT INTO users (username, email) VALUES (%s, %s)", (username, email)
        )

    categories = [
        ("Electronics", "Electronic devices and gadgets"),
        ("Clothing", "Fashion and apparel"),
        ("Books", "Books and literature"),
        ("Home & Garden", "Home improvement and gardening"),
    ]

    for name, desc in categories:
        cur.execute(
            "INSERT INTO categories (name, description) VALUES (%s, %s)", (name, desc)
        )

    products = [
        ("Laptop", "High-performance laptop", 899.99, 1),
        ("Smartphone", "Latest smartphone model", 699.99, 1),
        ("T-shirt", "Cotton t-shirt", 19.99, 2),
        ("Jeans", "Denim jeans", 49.99, 2),
        ("Python Programming", "Learn Python programming", 29.99, 3),
        ("Data Science Book", "Introduction to data science", 39.99, 3),
        ("Garden Hose", "50ft garden hose", 24.99, 4),
        ("Plant Pot", "Ceramic plant pot", 12.99, 4),
    ]

    for name, desc, price, cat_id in products:
        cur.execute(
            "INSERT INTO products (name, description, price, category_id) VALUES (%s, %s, %s, %s)",
            (name, desc, price, cat_id),
        )

    for i in range(10):
        user_id = random.randint(1, 5)
        order_date = datetime.now() - timedelta(days=random.randint(0, 30))
        cur.execute(
            "INSERT INTO orders (user_id, order_date) VALUES (%s, %s) RETURNING id",
            (user_id, order_date),
        )
        order_id = cur.fetchone()[0]

        num_items = random.randint(1, 4)
        total_amount = 0

        for _ in range(num_items):
            product_id = random.randint(1, 8)
            quantity = random.randint(1, 3)

            cur.execute("SELECT price FROM products WHERE id = %s", (product_id,))
            unit_price = cur.fetchone()[0]

            cur.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, unit_price),
            )

            total_amount += unit_price * quantity

        cur.execute(
            "UPDATE orders SET total_amount = %s WHERE id = %s",
            (total_amount, order_id),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("Data populated successfully!")
    print("Your DATABASE_URL is: postgresql://user:password@localhost:5432/testdb")
    print("You can now run main.py to test the SQL NLP Bot with this database.")


if __name__ == "__main__":
    populate_data()
