"""RFC 7396 merge-patch unit tests (S40)."""

from archiverr.state.merge import merge_patch


def test_null_deletes_key():
    assert merge_patch({"a": 1, "b": 2}, {"b": None}) == {"a": 1}


def test_nested_merge():
    target = {"jobs": {"j1": {"plugins": {"tmdb": {"show": {"title": "A"}}}}}}
    patch = {"jobs": {"j1": {"plugins": {"tmdb": {"show": {"year": 2008}}}}}}
    out = merge_patch(target, patch)
    assert out["jobs"]["j1"]["plugins"]["tmdb"]["show"] == {
        "title": "A",
        "year": 2008,
    }


def test_scalar_replaces():
    assert merge_patch({"a": {"b": 1}}, {"a": 2}) == {"a": 2}


def test_does_not_mutate_target():
    target = {"a": 1}
    merge_patch(target, {"b": 2})
    assert target == {"a": 1}
