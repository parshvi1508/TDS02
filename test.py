import sqlite3

# Create and connect to catalog.db
conn = sqlite3.connect("catalog.db")
cursor = conn.cursor()

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    category_id INTEGER,
    price REAL,
    stock INTEGER,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
)
""")

# Insert sample categories
categories = [
    ("Electronics",),
    ("Books",),
    ("Clothing",),
    ("Home Appliances",),
    ("Toys",)
]
cursor.executemany("INSERT INTO categories (category_name) VALUES (?)", categories)

# Insert sample products
products = [
    ("Smartphone", 1, 699.99, 50),
    ("Laptop", 1, 1200.00, 30),
    ("Science Fiction Novel", 2, 15.50, 100),
    ("Cookbook", 2, 22.00, 40),
    ("Men's T-shirt", 3, 12.99, 200),
    ("Women's Jeans", 3, 35.00, 150),
    ("Microwave Oven", 4, 99.99, 25),
    ("Refrigerator", 4, 450.00, 10),
    ("Board Game", 5, 29.99, 80),
    ("Action Figure", 5, 14.99, 120)
]
cursor.executemany("""
INSERT INTO products (product_name, category_id, price, stock)
VALUES (?, ?, ?, ?)
""", products)

# Commit and close
conn.commit()
conn.close()

print("catalog.db created successfully!")
