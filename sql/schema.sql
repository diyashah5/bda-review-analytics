-- Star schema for the review warehouse (PostgreSQL)
-- Dimensions describe things (product, category, price band, sentiment).
-- The fact table holds one row per cleaned review.

DROP TABLE IF EXISTS fact_reviews, dim_product, dim_category, dim_price_band, dim_sentiment CASCADE;

CREATE TABLE dim_category (
    category_key  INT  PRIMARY KEY,
    category_name TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_key  INT  PRIMARY KEY,
    product_name TEXT NOT NULL,
    category_key INT  NOT NULL REFERENCES dim_category (category_key)
);

CREATE TABLE dim_price_band (
    price_band_key INT  PRIMARY KEY,
    price_band     TEXT NOT NULL
);

CREATE TABLE dim_sentiment (
    sentiment_key INT  PRIMARY KEY,
    sentiment     TEXT NOT NULL
);

CREATE TABLE fact_reviews (
    review_key     BIGINT PRIMARY KEY,
    product_key    INT    NOT NULL REFERENCES dim_product (product_key),
    price_band_key INT    NOT NULL REFERENCES dim_price_band (price_band_key),
    sentiment_key  INT    NOT NULL REFERENCES dim_sentiment (sentiment_key),
    rating         SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    price          NUMERIC(12, 2) NOT NULL,
    word_count     INT    NOT NULL,
    review_text    TEXT   NOT NULL
);

CREATE INDEX idx_fact_product   ON fact_reviews (product_key);
CREATE INDEX idx_fact_sentiment ON fact_reviews (sentiment_key);
CREATE INDEX idx_fact_band      ON fact_reviews (price_band_key);
