CREATE TABLE customers (
  customer_id integer PRIMARY KEY,
  email text NOT NULL,
  region text NOT NULL CHECK (region IN ('EU', 'NA', 'APAC')),
  country text NOT NULL,
  created_at date NOT NULL
);

CREATE TABLE products (
  product_id integer PRIMARY KEY,
  name text NOT NULL,
  category text NOT NULL
);

CREATE TABLE orders (
  order_id integer PRIMARY KEY,
  customer_id integer NOT NULL REFERENCES customers(customer_id),
  ordered_at date NOT NULL,
  total_amount numeric(12, 2) NOT NULL CHECK (total_amount >= 0),
  channel text NOT NULL
);

CREATE TABLE order_items (
  order_item_id integer PRIMARY KEY,
  order_id integer NOT NULL REFERENCES orders(order_id),
  product_id integer NOT NULL REFERENCES products(product_id),
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_price numeric(12, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE payments (
  payment_id integer PRIMARY KEY,
  order_id integer NOT NULL UNIQUE REFERENCES orders(order_id),
  amount numeric(12, 2) NOT NULL,
  status text NOT NULL
);

CREATE TABLE refunds (
  refund_id integer PRIMARY KEY,
  order_id integer NOT NULL UNIQUE REFERENCES orders(order_id),
  amount numeric(12, 2) NOT NULL CHECK (amount >= 0),
  reason text NOT NULL,
  refunded_at date NOT NULL
);

CREATE TABLE shipments (
  shipment_id integer PRIMARY KEY,
  order_id integer NOT NULL UNIQUE REFERENCES orders(order_id),
  promised_at date NOT NULL,
  delivered_at date NOT NULL
);

INSERT INTO customers VALUES
  (1, 'eu-one@example.test', 'EU', 'DE', '2026-01-10'),
  (2, 'eu-two@example.test', 'EU', 'FR', '2026-01-12'),
  (3, 'eu-three@example.test', 'EU', 'NL', '2026-02-01'),
  (4, 'na-one@example.test', 'NA', 'US', '2026-01-15'),
  (5, 'na-two@example.test', 'NA', 'CA', '2026-02-10'),
  (6, 'apac-one@example.test', 'APAC', 'IN', '2026-03-01');

INSERT INTO products VALUES
  (1, 'Trail Shoes', 'footwear'),
  (2, 'City Jacket', 'apparel'),
  (3, 'Travel Pack', 'accessories'),
  (4, 'Insulated Bottle', 'accessories');

INSERT INTO orders VALUES
  (1, 1, '2026-06-05', 100.00, 'web'),
  (2, 2, '2026-06-10', 120.00, 'web'),
  (3, 3, '2026-06-18', 80.00, 'partner'),
  (4, 1, '2026-06-25', 100.00, 'web'),
  (5, 1, '2026-07-04', 100.00, 'web'),
  (6, 2, '2026-07-09', 120.00, 'web'),
  (7, 3, '2026-07-17', 80.00, 'partner'),
  (8, 1, '2026-07-24', 100.00, 'web'),
  (9, 4, '2026-07-06', 140.00, 'web'),
  (10, 5, '2026-07-13', 90.00, 'partner'),
  (11, 6, '2026-07-15', 110.00, 'web'),
  (12, 4, '2026-07-28', 60.00, 'web');

INSERT INTO order_items
SELECT order_id, order_id, ((order_id - 1) % 4) + 1, 1, total_amount
FROM orders;

INSERT INTO payments
SELECT order_id, order_id, total_amount, 'captured'
FROM orders;

INSERT INTO refunds VALUES
  (1, 2, 20.00, 'size_issue', '2026-06-20'),
  (2, 5, 90.00, 'shipping_delay', '2026-07-15'),
  (3, 6, 100.00, 'shipping_delay', '2026-07-20'),
  (4, 7, 70.00, 'shipping_delay', '2026-07-27'),
  (5, 10, 15.00, 'damaged', '2026-07-25');

INSERT INTO shipments
SELECT
  order_id,
  order_id,
  ordered_at + 4,
  ordered_at + CASE WHEN order_id IN (5, 6, 7) THEN 11 ELSE 3 END
FROM orders;

CREATE VIEW commerce_facts AS
SELECT
  o.order_id,
  o.customer_id,
  o.ordered_at,
  o.total_amount,
  o.channel,
  c.region,
  c.country,
  p.category,
  COALESCE(r.amount, 0)::numeric(12, 2) AS refund_amount,
  r.reason AS refund_reason,
  (s.delivered_at - s.promised_at) AS shipping_delay_days,
  COUNT(*) OVER (PARTITION BY o.customer_id) AS customer_order_count
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN refunds r ON r.order_id = o.order_id
JOIN shipments s ON s.order_id = o.order_id;
