CREATE DATABASE IF NOT EXISTS microsoft_stocks;
USE microsoft_stocks;

CREATE TABLE IF NOT EXISTS stocks (
    stock_id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_prices (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    trading_date DATETIME NOT NULL,
    open_price DECIMAL(12,4),
    high_price DECIMAL(12,4),
    low_price DECIMAL(12,4),
    close_price DECIMAL(12,4),
    volume BIGINT,

    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    UNIQUE (stock_id, trading_date)
);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    forecast_date DATETIME NOT NULL,
    predicted_close DECIMAL(12,4),
    model_version VARCHAR(50),

    FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

INSERT IGNORE INTO stocks (ticker, company_name)
VALUES ('MSFT', 'Microsoft Corporation');