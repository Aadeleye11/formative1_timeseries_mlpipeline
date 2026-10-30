
USE microsoft_stocks;

-- 1. Get the latest stock record
SELECT *
FROM stock_prices
ORDER BY trading_date DESC
LIMIT 1;


-- 2. Get stock records from January 2020
SELECT *
FROM stock_prices
WHERE trading_date >= '2020-01-01'
AND trading_date < '2020-02-01'
ORDER BY trading_date;


-- 3. Get the average closing price for each year
SELECT
    YEAR(trading_date) AS year,
    ROUND(AVG(close_price), 2) AS average_price
FROM stock_prices
GROUP BY YEAR(trading_date)
ORDER BY year;