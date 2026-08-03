from app.utils import TTLCache, content_to_text, iter_leaves, sha256_hex


def test_sha256_hex_is_deterministic_and_order_sensitive():
    assert sha256_hex("a", "b") == sha256_hex("a", "b")
    assert sha256_hex("a", "b") != sha256_hex("b", "a")


def test_ttlcache_flags_a_repeat_key_as_seen():
    cache = TTLCache(ttl_seconds=300)
    assert cache.seen("k") is False  # first time: not a duplicate
    assert cache.seen("k") is True  # second time: duplicate


def test_ttlcache_evicts_after_ttl_expires(monkeypatch):
    import app.utils as utils_module

    cache = TTLCache(ttl_seconds=10)
    clock = {"now": 0.0}
    monkeypatch.setattr(utils_module.time, "monotonic", lambda: clock["now"])

    assert cache.seen("k") is False
    clock["now"] = 11.0  # past the ttl
    assert cache.seen("k") is False  # evicted, so it's fresh again


def test_iter_leaves_walks_nested_dicts_and_lists():
    nested = {"a": 1, "b": [2, {"c": 3}], "d": "x"}
    assert sorted(iter_leaves(nested), key=str) == [1, 2, 3, "x"]


def test_content_to_text_handles_plain_string():
    assert content_to_text("plain text") == "plain text"


def test_content_to_text_handles_gemini_style_content_blocks():
    # ChatGoogleGenerativeAI can return response.content as a list of parts, not a str
    assert (
        content_to_text(
            [
                {"type": "text", "text": "part one "},
                {"type": "text", "text": "part two"},
            ]
        )
        == "part one part two"
    )
