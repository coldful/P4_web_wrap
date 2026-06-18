from p4_web.core.slug import slugify


def test_slugify_keeps_safe_ascii() -> None:
    assert slugify("Marine Project 001") == "marine-project-001"


def test_slugify_has_fallback() -> None:
    assert slugify("  !!!  ") == "project"

