
import os
from pathlib import Path

import pandas as pd
import mysql.connector
from pymongo import MongoClient
from dotenv import load_dotenv



# 1. Load environment vars

# Find the project root
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# 2. Load MS Stock Dataset

df = pd.read_csv(
    BASE_DIR / "data" / "raw" / "Microsoft_Stock.csv"
)

# Convert dates and sort 
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date").reset_index(drop=True)

# Check data quality
required_columns = [
    "Date", "Open", "High", "Low", "Close", "Volume"
]

if df[required_columns].isnull().any().any():
    raise ValueError("Dataset contains missing values. Clean them before importing.")

if df["Date"].duplicated().any():
    raise ValueError("Dataset contains duplicate dates. Review them before importing.")

print("Dataset loaded successfully!")
print("Total records:", len(df))


# 3. Connect to MySQL

mysql_connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE", "microsoft_stocks")
)

cursor = mysql_connection.cursor()

print("\nConnected to MySQL!")


# 4. Import data into MySQL

# Get Microsoft's stock ID
cursor.execute(
    "SELECT stock_id FROM stocks WHERE ticker = 'MSFT'"
)

result = cursor.fetchone()

if result is None:
    raise ValueError("MSFT not found. Run schema.sql first.")

stock_id = result[0]

query = """
INSERT INTO stock_prices
(stock_id, trading_date, open_price, high_price,
 low_price, close_price, volume)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    open_price = VALUES(open_price),
    high_price = VALUES(high_price),
    low_price = VALUES(low_price),
    close_price = VALUES(close_price),
    volume = VALUES(volume)
"""

for _, row in df.iterrows():
    values = (
        stock_id,
        row["Date"].to_pydatetime(),
        float(row["Open"]),
        float(row["High"]),
        float(row["Low"]),
        float(row["Close"]),
        int(row["Volume"])
    )

    cursor.execute(query, values)

mysql_connection.commit()

print("Data imported into MySQL successfully!")

# Verify the number of records
cursor.execute("SELECT COUNT(*) FROM stock_prices")

print("MySQL records:", cursor.fetchone()[0])

cursor.close()
mysql_connection.close()


# =5. Connect to MongDB

mongo_client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
)

mongo_client.admin.command("ping")

mongo_db = mongo_client["microsoft_stocks"]
collection = mongo_db["stock_prices"]

print("\nConnected to MongoDB!")

# Create unique index
collection.create_index(
    [("ticker", 1), ("date", 1)],
    unique=True
)


# 6. Import data into Mongo
for _, row in df.iterrows():

    document = {
        "ticker": "MSFT",
        "date": row["Date"].to_pydatetime(),
        "open": float(row["Open"]),
        "high": float(row["High"]),
        "low": float(row["Low"]),
        "close": float(row["Close"]),
        "volume": int(row["Volume"])
    }

    collection.replace_one(
        {
            "ticker": "MSFT",
            "date": document["date"]
        },
        document,
        upsert=True
    )

print("Data imported into MongoDB successfully!")

# Verify MongoDB records
mongo_count = collection.count_documents({"ticker": "MSFT"})

print("MongoDB records:", mongo_count)

mongo_client.close()




print("\n-------------------------------")
print("DATABASE IMPORT COMPLETED")
print("----------------------------------")
print("Dataset records:", len(df))
print("MongoDB records:", mongo_count)
print("Both databases have been populated.")
