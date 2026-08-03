#!/usr/bin/env python3
"""Tests for apply_sql.py. Standard library only, no pip dependency.

    python3 scripts/lib/test_apply_sql.py

Covers the two things in this file that fail SILENTLY when wrong:

  * split_statements -- a mis-split does not error, it sends half a statement,
    and the DDL here has semicolons inside string literals and inside comments.
  * redact -- a missed secret is printed to the terminal and into any captured
    log, with no indication anything went wrong.
"""

import unittest
from apply_sql import escape_sql_string, redact, split_statements, summarise


class TestSplitStatements(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(len(split_statements("SELECT 1; SELECT 2;")), 2)

    def test_trailing_statement_without_semicolon(self):
        self.assertEqual(len(split_statements("SELECT 1; SELECT 2")), 2)

    def test_semicolon_inside_single_quotes_does_not_split(self):
        # This is the real shape: 040's migration guard and every throwIf message
        # embed punctuation, and 022's guards contain 'TRUNCATE ...; and re-run'.
        sql = "SELECT throwIf(1=0, 'do this; then that'); SELECT 2"
        self.assertEqual(len(split_statements(sql)), 2)

    def test_semicolon_inside_line_comment_does_not_split(self):
        sql = "SELECT 1 -- a; b; c\n; SELECT 2"
        self.assertEqual(len(split_statements(sql)), 2)

    def test_semicolon_inside_block_comment_does_not_split(self):
        sql = "SELECT 1 /* a; b */; SELECT 2"
        self.assertEqual(len(split_statements(sql)), 2)

    def test_doubled_quote_escape(self):
        sql = "SELECT 'it''s; fine'; SELECT 2"
        self.assertEqual(len(split_statements(sql)), 2)

    def test_backslash_quote_escape(self):
        # Exactly how the clip_variant CAST is written throughout pipeline/sql.
        sql = ("SELECT CAST('unclipped', 'Enum8(\\'unclipped\\' = 1, \\'clipped\\' = 2)');"
               " SELECT 2")
        self.assertEqual(len(split_statements(sql)), 2)

    def test_backtick_and_double_quoted_identifiers(self):
        sql = 'SELECT `a;b`, "c;d" FROM t; SELECT 2'
        self.assertEqual(len(split_statements(sql)), 2)

    def test_comment_only_statements_are_dropped(self):
        self.assertEqual(split_statements("-- just a comment\n;"), [])

    def test_empty_input(self):
        self.assertEqual(split_statements(""), [])


class TestRedact(unittest.TestCase):
    def test_plain_secret(self):
        self.assertNotIn("hunter2", redact("PASSWORD 'hunter2'", "hunter2"))

    def test_escaped_form_is_also_redacted(self):
        """The regression this test exists for.

        The statement holds the SQL-ESCAPED password, so redacting only the raw
        spelling silently leaks any secret containing a quote or a backslash.
        """
        secret = "p@ss\\/w0rd'x"
        stmt = f"PASSWORD '{escape_sql_string(secret)}'"
        out = redact(stmt, secret)
        self.assertNotIn(secret, out)
        self.assertNotIn(escape_sql_string(secret), out)
        self.assertIn("********", out)

    def test_quote_and_backslash_variants(self):
        for secret in ["simple", "has'quote", "has\\backslash", 'has"double',
                       "both'\\mixed", "a'b\\c'd"]:
            with self.subTest(secret=secret):
                stmt = f"USER 'u' PASSWORD '{escape_sql_string(secret)}'"
                out = redact(stmt, secret)
                self.assertNotIn(secret, out, "raw form leaked")
                self.assertNotIn(escape_sql_string(secret), out, "escaped form leaked")

    def test_empty_secret_is_a_noop(self):
        self.assertEqual(redact("nothing to hide", ""), "nothing to hide")

    def test_secret_appearing_twice(self):
        self.assertEqual(redact("a s b s", "s").count("********"), 2)


class TestEscapeSQLString(unittest.TestCase):
    def test_matches_go_escapeSQLString(self):
        # Backslash first, then quote -- the order matters, or the escape of the
        # quote gets escaped again.
        self.assertEqual(escape_sql_string("a'b"), "a\\'b")
        self.assertEqual(escape_sql_string("a\\b"), "a\\\\b")
        self.assertEqual(escape_sql_string("a\\'b"), "a\\\\\\'b")


class TestSummarise(unittest.TestCase):
    def test_skips_leading_comments(self):
        # 040's producer begins with a comment block; a naive first-line summary
        # reports the comment instead of the statement.
        stmt = "-- a comment\n-- another\nINSERT INTO t SELECT 1"
        self.assertTrue(summarise(stmt).startswith("INSERT INTO t"))

    def test_truncates_with_ellipsis(self):
        self.assertTrue(summarise("SELECT " + "x" * 300, 40).endswith("…"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
