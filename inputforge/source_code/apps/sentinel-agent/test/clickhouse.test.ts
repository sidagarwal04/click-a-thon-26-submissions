import assert from "node:assert/strict";
import test from "node:test";
import { UnsafeQueryError, validateReadOnlySql } from "../agent/clickhouse.ts";

function assertUnsafe(sql: string, message: string) {
  assert.throws(
    () => validateReadOnlySql(sql),
    (error: unknown) => error instanceof UnsafeQueryError && error.message === message,
  );
}

test("accepts one bounded SELECT or WITH statement", () => {
  assert.equal(validateReadOnlySql("SELECT 1 LIMIT 1"), "SELECT 1 LIMIT 1");
  assert.equal(
    validateReadOnlySql("WITH 1 AS value SELECT value LIMIT 1;"),
    "WITH 1 AS value SELECT value LIMIT 1",
  );
});

test("rejects query types outside the read-only contract", () => {
  assertUnsafe("SHOW TABLES", "Only SELECT/WITH queries are allowed.");
  assertUnsafe("INSERT INTO inmobi.ad_events VALUES (1)", "Only SELECT/WITH queries are allowed.");
  assertUnsafe("SELECT 1", "Every query must include a numeric LIMIT.");
});

test("rejects comment and multi-statement bypasses", () => {
  assertUnsafe("SELECT 1 LIMIT 1; SELECT 2 LIMIT 1", "Only one uncommented SELECT/WITH statement is allowed.");
  assertUnsafe("SELECT 1 -- harmless\nLIMIT 1", "Only one uncommented SELECT/WITH statement is allowed.");
  assertUnsafe("SELECT /* comment */ 1 LIMIT 1", "Only one uncommented SELECT/WITH statement is allowed.");
});

test("rejects mutation keywords even when the statement begins with SELECT", () => {
  assertUnsafe(
    "SELECT 'drop' AS text LIMIT 1",
    "Query contains a keyword that is not allowed for read-only investigation.",
  );
});
