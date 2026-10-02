-- Analysis queries on the star schema. Each block starts with "-- name:".
-- They are run by scripts/06_sql_report.py (or paste them into any SQL client).

-- name: 1. Reviews and average rating by category
SELECT c.category_name, COUNT(*) AS reviews, ROUND(AVG(f.rating), 2) AS avg_rating
FROM fact_reviews f
JOIN dim_product p  ON f.product_key = p.product_key
JOIN dim_category c ON p.category_key = c.category_key
GROUP BY c.category_name
ORDER BY reviews DESC;

-- name: 2. Sentiment share by category (%)
SELECT c.category_name,
       ROUND(100.0 * SUM(CASE WHEN s.sentiment = 'positive' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_positive,
       ROUND(100.0 * SUM(CASE WHEN s.sentiment = 'neutral'  THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_neutral,
       ROUND(100.0 * SUM(CASE WHEN s.sentiment = 'negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_negative
FROM fact_reviews f
JOIN dim_product p   ON f.product_key = p.product_key
JOIN dim_category c  ON p.category_key = c.category_key
JOIN dim_sentiment s ON f.sentiment_key = s.sentiment_key
GROUP BY c.category_name
ORDER BY pct_positive DESC;

-- name: 3. Average rating and review length by price band
SELECT b.price_band, COUNT(*) AS reviews,
       ROUND(AVG(f.rating), 2) AS avg_rating,
       ROUND(AVG(f.word_count), 1) AS avg_words
FROM fact_reviews f
JOIN dim_price_band b ON f.price_band_key = b.price_band_key
GROUP BY b.price_band
ORDER BY b.price_band;

-- name: 4. Rating distribution
SELECT rating, COUNT(*) AS reviews,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM fact_reviews
GROUP BY rating
ORDER BY rating;

-- name: 5. Top 10 most reviewed products
SELECT LEFT(p.product_name, 60) AS product, c.category_name,
       COUNT(*) AS reviews, ROUND(AVG(f.rating), 2) AS avg_rating
FROM fact_reviews f
JOIN dim_product p  ON f.product_key = p.product_key
JOIN dim_category c ON p.category_key = c.category_key
GROUP BY p.product_name, c.category_name
ORDER BY reviews DESC
LIMIT 10;

-- name: 6. Products with the highest share of negative reviews (200+ reviews)
SELECT LEFT(p.product_name, 60) AS product, COUNT(*) AS reviews,
       ROUND(100.0 * SUM(CASE WHEN s.sentiment = 'negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_negative
FROM fact_reviews f
JOIN dim_product p   ON f.product_key = p.product_key
JOIN dim_sentiment s ON f.sentiment_key = s.sentiment_key
GROUP BY p.product_name
HAVING COUNT(*) >= 200
ORDER BY pct_negative DESC
LIMIT 10;

-- name: 7. Average rating by category and price band (100+ reviews)
SELECT c.category_name, b.price_band, COUNT(*) AS reviews, ROUND(AVG(f.rating), 2) AS avg_rating
FROM fact_reviews f
JOIN dim_product p     ON f.product_key = p.product_key
JOIN dim_category c    ON p.category_key = c.category_key
JOIN dim_price_band b  ON f.price_band_key = b.price_band_key
GROUP BY c.category_name, b.price_band
HAVING COUNT(*) >= 100
ORDER BY c.category_name, b.price_band;

-- name: 8. Review length and price by sentiment
SELECT s.sentiment, COUNT(*) AS reviews,
       ROUND(AVG(f.word_count), 1) AS avg_words,
       ROUND(AVG(f.price), 0) AS avg_price
FROM fact_reviews f
JOIN dim_sentiment s ON f.sentiment_key = s.sentiment_key
GROUP BY s.sentiment
ORDER BY s.sentiment;

-- name: 9. Best rated product in each category (window function, 100+ reviews)
WITH product_stats AS (
    SELECT c.category_name, p.product_name,
           COUNT(*) AS reviews, ROUND(AVG(f.rating), 2) AS avg_rating
    FROM fact_reviews f
    JOIN dim_product p  ON f.product_key = p.product_key
    JOIN dim_category c ON p.category_key = c.category_key
    GROUP BY c.category_name, p.product_name
    HAVING COUNT(*) >= 100
), ranked AS (
    SELECT *, RANK() OVER (PARTITION BY category_name
                           ORDER BY avg_rating DESC, reviews DESC) AS rnk
    FROM product_stats
)
SELECT category_name, LEFT(product_name, 55) AS product, reviews, avg_rating
FROM ranked
WHERE rnk = 1
ORDER BY category_name;

-- name: 10. Model results stored in the warehouse
SELECT model, metric, value FROM gold_model_metrics ORDER BY model, metric;
