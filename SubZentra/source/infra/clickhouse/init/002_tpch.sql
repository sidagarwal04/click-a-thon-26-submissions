-- A TPC-H subset, as a Data Source the Connector can be pointed at.
--
-- This is customer-shaped data, deliberately in its own database and nothing to
-- do with `zentra_audit` beside it — the ledger holds no raw values and putting
-- analytical rows in it would make that a matter of which table you read.
--
-- Fully deterministic: `numbers()` and modular arithmetic, never `rand()`. A
-- fresh `docker compose up` reproduces this byte for byte, which is what lets
-- the inference accuracy harness assert a number rather than a range.
--
-- Scaled down from SF-1 but *not* uniformly. Key cardinalities are what the
-- cardinality ceiling reacts to, so customer and orders stay well above the
-- 1,000-distinct threshold where confidence stops being capped. Shrinking them
-- to a convenient size would exercise a bound the real dataset never hits.
--
-- The nine relationships below are TPC-H's documented foreign keys, and they
-- are the ground truth `tools/evals/connector_accuracy.py` scores against:
--
--   customer.c_nationkey -> nation.n_nationkey
--   supplier.s_nationkey -> nation.n_nationkey
--   nation.n_regionkey   -> region.r_regionkey
--   orders.o_custkey     -> customer.c_custkey
--   lineitem.l_orderkey  -> orders.o_orderkey
--   lineitem.l_partkey   -> part.p_partkey
--   lineitem.l_suppkey   -> supplier.s_suppkey
--   partsupp.ps_partkey  -> part.p_partkey
--   partsupp.ps_suppkey  -> supplier.s_suppkey

CREATE DATABASE IF NOT EXISTS tpch;

CREATE TABLE IF NOT EXISTS tpch.region (
    r_regionkey UInt32,
    r_name String,
    r_comment String
) ENGINE = MergeTree ORDER BY r_regionkey;

CREATE TABLE IF NOT EXISTS tpch.nation (
    n_nationkey UInt32,
    n_name String,
    n_regionkey UInt32,
    n_comment String
) ENGINE = MergeTree ORDER BY n_nationkey;

CREATE TABLE IF NOT EXISTS tpch.supplier (
    s_suppkey UInt32,
    s_name String,
    s_nationkey UInt32,
    s_acctbal Decimal(12, 2)
) ENGINE = MergeTree ORDER BY s_suppkey;

CREATE TABLE IF NOT EXISTS tpch.customer (
    c_custkey UInt32,
    c_name String,
    c_nationkey UInt32,
    c_acctbal Decimal(12, 2),
    c_mktsegment String
) ENGINE = MergeTree ORDER BY c_custkey;

CREATE TABLE IF NOT EXISTS tpch.part (
    p_partkey UInt32,
    p_name String,
    p_brand String,
    p_retailprice Decimal(12, 2)
) ENGINE = MergeTree ORDER BY p_partkey;

CREATE TABLE IF NOT EXISTS tpch.partsupp (
    ps_partkey UInt32,
    ps_suppkey UInt32,
    ps_availqty UInt32,
    ps_supplycost Decimal(12, 2)
) ENGINE = MergeTree ORDER BY (ps_partkey, ps_suppkey);

CREATE TABLE IF NOT EXISTS tpch.orders (
    o_orderkey UInt32,
    o_custkey UInt32,
    o_orderstatus String,
    o_totalprice Decimal(12, 2),
    o_orderdate Date
) ENGINE = MergeTree ORDER BY o_orderkey;

CREATE TABLE IF NOT EXISTS tpch.lineitem (
    l_orderkey UInt32,
    l_partkey UInt32,
    l_suppkey UInt32,
    l_linenumber UInt32,
    l_quantity Decimal(12, 2),
    l_extendedprice Decimal(12, 2),
    l_shipdate Date
) ENGINE = MergeTree ORDER BY (l_orderkey, l_linenumber);

-- 5 regions
INSERT INTO tpch.region
SELECT number, concat('REGION', toString(number)), 'r'
FROM numbers(5);

-- 25 nations, 5 per region
INSERT INTO tpch.nation
SELECT number, concat('NATION', toString(number)), number % 5, 'n'
FROM numbers(25);

-- 2,000 suppliers
INSERT INTO tpch.supplier
SELECT number + 1, concat('Supplier#', toString(number + 1)), number % 25,
       toDecimal64(1000 + (number % 9000), 2)
FROM numbers(2000);

-- 15,000 customers. Well above the 1,000-distinct cardinality threshold.
INSERT INTO tpch.customer
SELECT number + 1, concat('Customer#', toString(number + 1)), number % 25,
       toDecimal64((number % 10000), 2),
       ['AUTOMOBILE', 'BUILDING', 'FURNITURE', 'MACHINERY', 'HOUSEHOLD'][(number % 5) + 1]
FROM numbers(15000);

-- 4,000 parts
INSERT INTO tpch.part
SELECT number + 1, concat('part-', toString(number + 1)),
       concat('Brand#', toString((number % 25) + 10)),
       toDecimal64(900 + (number % 1100), 2)
FROM numbers(4000);

-- 8,000 partsupp rows: 2 suppliers per part for the first 4,000 parts
INSERT INTO tpch.partsupp
SELECT (number % 4000) + 1,
       ((number * 7) % 2000) + 1,
       number % 9999,
       toDecimal64(1 + (number % 1000), 2)
FROM numbers(8000);

-- 60,000 orders across 15,000 customers
INSERT INTO tpch.orders
SELECT number + 1,
       (number % 15000) + 1,
       ['O', 'F', 'P'][(number % 3) + 1],
       toDecimal64(1000 + (number % 90000), 2),
       toDate('2026-01-01') + (number % 365)
FROM numbers(60000);

-- 240,000 lineitems: 4 per order
INSERT INTO tpch.lineitem
SELECT (number % 60000) + 1,
       ((number * 13) % 4000) + 1,
       ((number * 11) % 2000) + 1,
       (number % 4) + 1,
       toDecimal64(1 + (number % 50), 2),
       toDecimal64(100 + (number % 9000), 2),
       toDate('2026-01-05') + (number % 360)
FROM numbers(240000);

-- A read-only user for the Connector to register as a Data Source. Read-only on
-- purpose: discovery reads schema and computes aggregates, and a harvest that
-- could write to a customer's warehouse would be a capability nobody asked for.
CREATE USER IF NOT EXISTS tpch_reader IDENTIFIED WITH plaintext_password BY 'tpch_reader';
GRANT SELECT ON tpch.* TO tpch_reader;
GRANT SELECT ON system.tables TO tpch_reader;
GRANT SELECT ON system.columns TO tpch_reader;
