CREATE DATABASE IF NOT EXISTS hackathon;

CREATE TABLE IF NOT EXISTS hackathon.events
(
    event_time  DateTime,
    user_id     UInt32,
    event_type  String,   -- 'page_view', 'click', 'signup', 'purchase'
    page        String,
    country     String,
    duration_ms UInt32,
    revenue     Decimal(10, 2)
)
ENGINE = MergeTree
ORDER BY event_time;

INSERT INTO hackathon.events VALUES
('2026-07-14 08:03:00', 101, 'page_view', '/home',     'IN', 1200, 0),
('2026-07-14 08:05:00', 101, 'click',     '/pricing',  'IN',  300, 0),
('2026-07-14 08:10:00', 101, 'signup',    '/signup',   'IN',  900, 0),
('2026-07-14 09:15:00', 102, 'page_view', '/home',     'US', 1400, 0),
('2026-07-14 09:18:00', 102, 'click',     '/blog',     'US',  500, 0),
('2026-07-14 10:22:00', 103, 'page_view', '/pricing',  'DE',  800, 0),
('2026-07-14 10:24:00', 103, 'purchase',  '/checkout', 'DE',  600, 49.99),
('2026-07-14 11:01:00', 104, 'page_view', '/home',     'IN', 1100, 0),
('2026-07-14 11:05:00', 104, 'click',     '/pricing',  'IN',  200, 0),
('2026-07-14 11:12:00', 104, 'purchase',  '/checkout', 'IN',  700, 19.99),
('2026-07-15 08:30:00', 105, 'page_view', '/home',     'GB', 1600, 0),
('2026-07-15 08:35:00', 105, 'click',     '/blog',     'GB',  450, 0),
('2026-07-15 09:40:00', 106, 'page_view', '/pricing',  'US',  950, 0),
('2026-07-15 09:44:00', 106, 'signup',    '/signup',   'US',  850, 0),
('2026-07-15 10:05:00', 107, 'page_view', '/home',     'IN', 1300, 0),
('2026-07-15 10:11:00', 107, 'purchase',  '/checkout', 'IN',  650, 29.99),
('2026-07-15 12:20:00', 108, 'page_view', '/blog',     'DE', 1000, 0),
('2026-07-15 12:26:00', 108, 'click',     '/pricing',  'DE',  300, 0),
('2026-07-16 08:12:00', 101, 'page_view', '/blog',     'IN',  700, 0),
('2026-07-16 08:20:00', 101, 'purchase',  '/checkout', 'IN',  400, 39.99),
('2026-07-16 09:05:00', 109, 'page_view', '/home',     'US', 1250, 0),
('2026-07-16 09:09:00', 109, 'click',     '/pricing',  'US',  350, 0),
('2026-07-16 09:14:00', 109, 'signup',    '/signup',   'US',  900, 0),
('2026-07-16 10:30:00', 110, 'page_view', '/home',     'GB', 1050, 0),
('2026-07-16 10:36:00', 110, 'purchase',  '/checkout', 'GB',  500, 59.99),
('2026-07-17 08:00:00', 111, 'page_view', '/pricing',  'IN',  900, 0),
('2026-07-17 08:06:00', 111, 'click',     '/blog',     'IN',  400, 0),
('2026-07-17 09:20:00', 112, 'page_view', '/home',     'DE', 1150, 0),
('2026-07-17 09:26:00', 112, 'purchase',  '/checkout', 'DE',  550, 24.99),
('2026-07-17 10:40:00', 113, 'page_view', '/home',     'US', 1400, 0);

-- Grain tables for the Analytics Agent (daily / weekly / monthly).
CREATE TABLE IF NOT EXISTS hackathon.revenue_daily
(
    fromDate Date,
    toDate   Date,
    revenue  Decimal(10, 2),
    country  String
)
ENGINE = MergeTree
ORDER BY (fromDate, country);

CREATE TABLE IF NOT EXISTS hackathon.revenue_weekly
(
    fromDate Date,
    toDate   Date,
    revenue  Decimal(10, 2),
    country  String
)
ENGINE = MergeTree
ORDER BY (fromDate, country);

CREATE TABLE IF NOT EXISTS hackathon.revenue_monthly
(
    fromDate Date,
    toDate   Date,
    revenue  Decimal(10, 2),
    country  String
)
ENGINE = MergeTree
ORDER BY (fromDate, country);

INSERT INTO hackathon.revenue_daily VALUES
('2026-07-14', '2026-07-14', 69.98, 'IN'),
('2026-07-14', '2026-07-14',  0.00, 'US'),
('2026-07-14', '2026-07-14', 49.99, 'DE'),
('2026-07-14', '2026-07-14',  0.00, 'GB'),
('2026-07-15', '2026-07-15', 29.99, 'IN'),
('2026-07-15', '2026-07-15',  0.00, 'US'),
('2026-07-15', '2026-07-15',  0.00, 'DE'),
('2026-07-15', '2026-07-15',  0.00, 'GB'),
('2026-07-16', '2026-07-16', 39.99, 'IN'),
('2026-07-16', '2026-07-16',  0.00, 'US'),
('2026-07-16', '2026-07-16',  0.00, 'DE'),
('2026-07-16', '2026-07-16', 59.99, 'GB'),
('2026-07-17', '2026-07-17',  0.00, 'IN'),
('2026-07-17', '2026-07-17',  0.00, 'US'),
('2026-07-17', '2026-07-17', 24.99, 'DE'),
('2026-07-17', '2026-07-17',  0.00, 'GB');

INSERT INTO hackathon.revenue_weekly VALUES
('2026-07-13', '2026-07-19', 139.96, 'IN'),
('2026-07-13', '2026-07-19',   0.00, 'US'),
('2026-07-13', '2026-07-19',  74.98, 'DE'),
('2026-07-13', '2026-07-19',  59.99, 'GB');

INSERT INTO hackathon.revenue_monthly VALUES
('2026-07-01', '2026-07-31', 139.96, 'IN'),
('2026-07-01', '2026-07-31',   0.00, 'US'),
('2026-07-01', '2026-07-31',  74.98, 'DE'),
('2026-07-01', '2026-07-31',  59.99, 'GB');
