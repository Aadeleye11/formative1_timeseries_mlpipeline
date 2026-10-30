use("microsoft_stocks");

// 1. Latest stock record
print("QUERY 1: Latest stock record");
printjson(
    db.stock_prices.find().sort({ date: -1 }).limit(1).toArray()
);

// 2. January 2020 records
print("QUERY 2: January 2020 records");
printjson(
    db.stock_prices.find({
        date: {
            $gte: ISODate("2020-01-01"),
            $lt: ISODate("2020-02-01")
        }
    }).sort({ date: 1 }).toArray()
);

// 3. Average closing price by year
print("QUERY 3: Average closing price by year");
printjson(
    db.stock_prices.aggregate([
        {
            $group: {
                _id: { $year: "$date" },
                average_price: { $avg: "$close" }
            }
        },
        { $sort: { _id: 1 } }
    ]).toArray()
);