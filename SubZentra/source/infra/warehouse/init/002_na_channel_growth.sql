-- North America channel growth, October to November 2026.
--
-- A second scenario with enough records to clear the sample-size ceiling, so
-- the publish path — finding straight to the user, no approval gate — is
-- reachable at all. The refund scenario in 001 has eight EU orders, which caps
-- confidence at 0.65 against a 0.7 threshold and can therefore only ever gate.
--
-- Deliberately disjoint from 001 on both axes that scenario filters on: region
-- NA, and dates from 2026-10 onward where 001 ends on 2026-07-28. The recorded
-- cassettes under evals/cassettes/ key on the exact prompt text, which contains
-- the query result, so a single extra row in the EU June-July slice would
-- invalidate all of them.
--
-- Fully deterministic — generate_series, no random() — so a fresh
-- `docker compose up` reproduces this byte for byte and the cassettes stay
-- valid.
--
--   month     web                 partner              orders  revenue
--   2026-10   100 x $100 = 10000   20 x $150 =  3000     120     13000
--   2026-11   100 x $100 = 10000   80 x $150 = 12000     180     22000
--
-- Web is identical across both months, so the entire +9000 is partner. 300
-- orders total, past the >= 100 band, so nothing caps a confident answer.

INSERT INTO customers
SELECT
  100 + g,
  'na-growth-' || g || '@example.test',
  'NA',
  CASE WHEN g % 3 = 0 THEN 'CA' ELSE 'US' END,
  DATE '2026-09-01'
FROM generate_series(1, 60) AS g;

-- g 1-100 web October, 101-120 partner October,
-- g 121-220 web November, 221-300 partner November.
INSERT INTO orders
SELECT
  1000 + g,
  100 + ((g - 1) % 60) + 1,
  -- Day of month from the series index, so every date stays inside its month.
  CASE WHEN g <= 120 THEN DATE '2026-10-01' ELSE DATE '2026-11-01' END
    + ((g - 1) % 28),
  CASE WHEN g BETWEEN 101 AND 120 OR g > 220 THEN 150.00 ELSE 100.00 END,
  CASE WHEN g BETWEEN 101 AND 120 OR g > 220 THEN 'partner' ELSE 'web' END
FROM generate_series(1, 300) AS g;

-- One item per order, exactly as 001 does. commerce_facts inner-joins
-- order_items, so a second item would duplicate the order's row and make every
-- sum measure double-count it.
INSERT INTO order_items
SELECT order_id, order_id, ((order_id - 1) % 4) + 1, 1, total_amount
FROM orders
WHERE order_id > 1000;

INSERT INTO payments
SELECT order_id, order_id, total_amount, 'captured'
FROM orders
WHERE order_id > 1000;

-- Delivered on time. No refunds either: this scenario is about where revenue
-- came from, and leaving the refund measures at zero here keeps it from
-- muddying the question 001 asks.
INSERT INTO shipments
SELECT order_id, order_id, ordered_at + 4, ordered_at + 3
FROM orders
WHERE order_id > 1000;
