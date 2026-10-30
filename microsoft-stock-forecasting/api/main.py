import os
from datetime import datetime
from pathlib import Path

import mysql.connector
from mysql.connector import IntegrityError
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# Load passwords and database settings from the project .env file
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Microsoft Stock API")


def mysql_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "microsoft_stocks"),
    )


mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"))
mongo_collection = mongo_client["microsoft_stocks"]["stock_prices"]


class StockRecord(BaseModel):
    date: datetime
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: int = Field(ge=0)


# Convert MySQL rows to JSON-friendly stock records
def sql_format(row):
    return {
        "id": row["record_id"],
        "date": row["trading_date"].isoformat(),
        "open": float(row["open_price"]),
        "high": float(row["high_price"]),
        "low": float(row["low_price"]),
        "close": float(row["close_price"]),
        "volume": row["volume"],
    }


def sql_select(query, values=(), one=False):
    conn = mysql_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, values)
        result = cursor.fetchone() if one else cursor.fetchall()
        if one:
            return sql_format(result) if result else None
        return [sql_format(row) for row in result]
    finally:
        cursor.close()
        conn.close()


SQL_COLUMNS = "record_id, trading_date, open_price, high_price, low_price, close_price, volume"


# Convert MongoDB documents to JSON-friendly stock records
def mongo_format(document):
    if document is None:
        return None
    document["id"] = str(document.pop("_id"))
    document["date"] = document["date"].isoformat()
    return document


def mongo_id(value):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid MongoDB ID")


@app.get("/")
def home():
    return {"message": "Microsoft Stock API is running"}


# ---------------- MYSQL ----------------

@app.get("/sql/stocks")
def sql_list(limit: int = Query(60, ge=1, le=500)):
    records = sql_select(
        f"SELECT {SQL_COLUMNS} FROM stock_prices ORDER BY trading_date DESC LIMIT %s",
        (limit,),
    )
    return list(reversed(records))


@app.get("/sql/stocks/latest")
def sql_latest():
    record = sql_select(
        f"SELECT {SQL_COLUMNS} FROM stock_prices ORDER BY trading_date DESC LIMIT 1",
        one=True,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="No records found")
    return record


@app.get("/sql/stocks/range")
def sql_range(start: datetime, end: datetime):
    if start > end:
        raise HTTPException(status_code=400, detail="start must not be after end")
    return sql_select(
        f"SELECT {SQL_COLUMNS} FROM stock_prices WHERE trading_date BETWEEN %s AND %s ORDER BY trading_date",
        (start, end),
    )


@app.get("/sql/stocks/{record_id}")
def sql_get(record_id: int):
    record = sql_select(
        f"SELECT {SQL_COLUMNS} FROM stock_prices WHERE record_id = %s",
        (record_id,),
        one=True,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@app.post("/sql/stocks", status_code=201)
def sql_create(record: StockRecord):
    conn = mysql_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT stock_id FROM stocks WHERE ticker = %s", ("MSFT",))
        stock = cursor.fetchone()
        if not stock:
            raise HTTPException(status_code=400, detail="MSFT is missing from stocks table")
        cursor.execute(
            """INSERT INTO stock_prices
               (stock_id, trading_date, open_price, high_price, low_price, close_price, volume)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (stock[0], record.date, record.open, record.high,
             record.low, record.close, record.volume),
        )
        new_id = cursor.lastrowid
        conn.commit()
    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="A record for that date already exists")
    finally:
        cursor.close()
        conn.close()
    return sql_get(new_id)


@app.put("/sql/stocks/{record_id}")
def sql_update(record_id: int, record: StockRecord):
    conn = mysql_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE stock_prices SET trading_date=%s, open_price=%s,
               high_price=%s, low_price=%s, close_price=%s, volume=%s
               WHERE record_id=%s""",
            (record.date, record.open, record.high, record.low,
             record.close, record.volume, record_id),
        )
        # MySQL may report 0 for an unchanged record; look it up afterward.
        conn.commit()
    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="A record for that date already exists")
    finally:
        cursor.close()
        conn.close()
    return sql_get(record_id)


@app.delete("/sql/stocks/{record_id}")
def sql_delete(record_id: int):
    conn = mysql_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM stock_prices WHERE record_id=%s", (record_id,))
        deleted = cursor.rowcount
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "MySQL record deleted"}


# ---------------- MONGODB ----------------

@app.get("/mongo/stocks")
def mongo_list(limit: int = Query(60, ge=1, le=500)):
    records = list(mongo_collection.find().sort("date", -1).limit(limit))
    return [mongo_format(record) for record in reversed(records)]


@app.get("/mongo/stocks/latest")
def mongo_latest():
    record = mongo_collection.find_one(sort=[("date", -1)])
    if record is None:
        raise HTTPException(status_code=404, detail="No records found")
    return mongo_format(record)


@app.get("/mongo/stocks/range")
def mongo_range(start: datetime, end: datetime):
    if start > end:
        raise HTTPException(status_code=400, detail="start must not be after end")
    records = mongo_collection.find({"date": {"$gte": start, "$lte": end}}).sort("date", 1)
    return [mongo_format(record) for record in records]


@app.get("/mongo/stocks/{record_id}")
def mongo_get(record_id: str):
    record = mongo_collection.find_one({"_id": mongo_id(record_id)})
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return mongo_format(record)


@app.post("/mongo/stocks", status_code=201)
def mongo_create(record: StockRecord):
    document = record.model_dump()
    document["ticker"] = "MSFT"
    try:
        new_id = mongo_collection.insert_one(document).inserted_id
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A record for that date already exists")
    return mongo_get(str(new_id))


@app.put("/mongo/stocks/{record_id}")
def mongo_update(record_id: str, record: StockRecord):
    document = record.model_dump()
    document["ticker"] = "MSFT"
    try:
        result = mongo_collection.update_one(
            {"_id": mongo_id(record_id)}, {"$set": document}
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A record for that date already exists")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return mongo_get(record_id)


@app.delete("/mongo/stocks/{record_id}")
def mongo_delete(record_id: str):
    result = mongo_collection.delete_one({"_id": mongo_id(record_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "MongoDB record deleted"}
