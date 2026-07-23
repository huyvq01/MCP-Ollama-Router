def test_cache_set_get(cache):
    cache.clear()

    cache.set(
        "name",
        "ChatGPT",
    )

    assert cache.get("name") == "ChatGPT"


def test_cache_default(cache):
    cache.clear()

    assert cache.get("unknown") is None


def test_cache_overwrite(cache):
    cache.clear()

    cache.set(
        "name",
        "A",
    )

    cache.set(
        "name",
        "B",
    )

    assert cache.get("name") == "B"


def test_cache_clear(cache):
    cache.set("a", 1)
    cache.set("b", 2)

    cache.clear()

    assert cache.get("a") is None
    assert cache.get("b") is None
