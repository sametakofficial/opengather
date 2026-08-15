"""Live TMDb smoke. Skipped unless TMDB_API_KEY is set."""

import os

import pytest

from archiverr.plugins.tmdb.utils.api import TMDbAPI


@pytest.mark.skipif(not os.environ.get("TMDB_API_KEY"), reason="TMDB_API_KEY not set")
def test_tmdb_finds_breaking_bad():
    api = TMDbAPI(os.environ["TMDB_API_KEY"], language="en-US", region="US")
    data = api.search_tv("Breaking Bad")
    results = data.get("results") or []
    assert results
    titles = {r.get("name") for r in results}
    assert "Breaking Bad" in titles
