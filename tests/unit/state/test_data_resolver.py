"""Unit tests for DataResolver + DataResolverProxy (S39 R15 §D1)."""

from archiverr.state.data_resolver import DataResolver, DataResolverProxy


def _make_lookup(plugin_data: dict[tuple[str | int, str], dict]):
    """Build a (scope, plugin_name) -> data lookup callable from a fixture map."""
    def _lookup(scope, plugin_name):
        return plugin_data.get((scope, plugin_name))
    return _lookup


class TestPriorityResolution:
    def test_first_plugin_wins(self):
        priority = {"data.<jobindex>.show": ["tmdb", "omdb", "tvmaze"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            (0, "tmdb"): {"show": {"title": {"primary": "TMDb-Title"}}},
            (0, "omdb"): {"show": {"title": {"primary": "OMDb-Title"}}},
        })
        out = resolver.resolve(
            "data.<jobindex>.show.title.primary", lookup, active_job_index=0,
        )
        assert out == "TMDb-Title"

    def test_falls_through_to_next_plugin(self):
        priority = {"data.<jobindex>.show": ["tmdb", "omdb"]}
        resolver = DataResolver(priority)
        # tmdb returns dict but path is missing => falls through to omdb.
        lookup = _make_lookup({
            (0, "tmdb"): {"show": {}},
            (0, "omdb"): {"show": {"title": {"primary": "OMDb"}}},
        })
        out = resolver.resolve(
            "data.<jobindex>.show.title.primary", lookup, active_job_index=0,
        )
        assert out == "OMDb"

    def test_returns_none_when_no_plugin_has_path(self):
        priority = {"data.<jobindex>.show": ["tmdb", "omdb"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            (0, "tmdb"): {"show": {}},
            (0, "omdb"): {"show": {}},
        })
        assert resolver.resolve(
            "data.<jobindex>.show.title.primary", lookup, active_job_index=0,
        ) is None


class TestLongestPrefixMatch:
    def test_specific_path_overrides_general(self):
        priority = {
            "data.<jobindex>.show":              ["tmdb", "omdb", "tvmaze"],
            "data.<jobindex>.show.episode_title": ["tmdb"],  # only tmdb
        }
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            (0, "tmdb"):   {"show": {"episode_title": "PilotTMDB"}},
            (0, "omdb"):   {"show": {"episode_title": "PilotOMDB"}},
            (0, "tvmaze"): {"show": {"episode_title": "PilotTVMaze"}},
        })
        out = resolver.resolve(
            "data.<jobindex>.show.episode_title", lookup, active_job_index=0,
        )
        assert out == "PilotTMDB"

    def test_general_falls_back_when_specific_misses(self):
        priority = {
            "data.<jobindex>.show":              ["tmdb", "omdb"],
            "data.<jobindex>.show.episode_title": ["tvmaze"],
        }
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            # tvmaze has no data → specific list yields nothing
            (0, "tvmaze"): {"show": {}},
            # tmdb / omdb cover the title path
            (0, "tmdb"):   {"show": {"title": {"primary": "T"}}},
            (0, "omdb"):   {},
        })
        # Lookup of show.title.primary doesn't match the more specific
        # "show.episode_title" key; falls through to "show" priority.
        out = resolver.resolve(
            "data.<jobindex>.show.title.primary", lookup, active_job_index=0,
        )
        assert out == "T"


class TestRunScope:
    def test_run_scope_priority(self):
        priority = {"data.run.scanner": ["scanner"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({("run", "scanner"): {"scanner": {"count": 5}}})
        out = resolver.resolve("data.run.scanner.count", lookup)
        assert out == 5

    def test_run_scope_no_active_job_index_required(self):
        priority = {"data.run.scanner": ["scanner"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({("run", "scanner"): {"scanner": {"count": 7}}})
        # active_job_index None should not affect run-scope resolution.
        assert resolver.resolve("data.run.scanner.count", lookup) == 7


class TestNumericIndex:
    def test_numeric_jobindex_in_path_resolves(self):
        priority = {"data.<jobindex>.show": ["tmdb"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            (0, "tmdb"): {"show": {"title": {"primary": "Job0"}}},
            (1, "tmdb"): {"show": {"title": {"primary": "Job1"}}},
        })
        # Numeric forms map to the corresponding job.
        assert resolver.resolve(
            "data.0.show.title.primary", lookup, active_job_index=0
        ) == "Job0"
        assert resolver.resolve(
            "data.1.show.title.primary", lookup, active_job_index=1
        ) == "Job1"


class TestEdgeCases:
    def test_unknown_path_returns_none(self):
        resolver = DataResolver({"data.<jobindex>.movie": ["tmdb"]})
        lookup = _make_lookup({(0, "tmdb"): {"movie": {}}})
        # No priority key matches "show.X"; resolve returns None.
        assert resolver.resolve(
            "data.<jobindex>.show.title.primary", lookup, active_job_index=0,
        ) is None

    def test_empty_priority_returns_none(self):
        resolver = DataResolver({})
        lookup = _make_lookup({(0, "tmdb"): {"show": {"x": 1}}})
        assert resolver.resolve(
            "data.<jobindex>.show.x", lookup, active_job_index=0,
        ) is None

    def test_malformed_path_returns_none(self):
        resolver = DataResolver({"data.<jobindex>.show": ["tmdb"]})
        lookup = _make_lookup({(0, "tmdb"): {"show": {"x": 1}}})
        # No active_job_index for sentinel form.
        assert resolver.resolve(
            "data.<jobindex>.show.x", lookup, active_job_index=None,
        ) is None

    def test_plugin_returns_non_dict_skipped(self):
        priority = {"data.<jobindex>.show": ["tmdb", "omdb"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            (0, "tmdb"): "not a dict",  # type: ignore[dict-item]
            (0, "omdb"): {"show": {"x": "ok"}},
        })
        assert resolver.resolve(
            "data.<jobindex>.show.x", lookup, active_job_index=0,
        ) == "ok"


class TestProxy:
    def test_attr_chain_resolves_str(self):
        priority = {"data.<jobindex>.show": ["tmdb"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            (0, "tmdb"): {"show": {"title": {"primary": "Inception"}}},
        })
        proxy = DataResolverProxy(resolver, lookup, active_index=0)
        # data.<jobindex>.show.title.primary form.
        chain = proxy["<jobindex>"].show.title.primary
        assert str(chain) == "Inception"

    def test_attr_chain_no_match_renders_empty(self):
        priority = {"data.<jobindex>.show": ["tmdb"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({(0, "tmdb"): {"show": {}}})
        proxy = DataResolverProxy(resolver, lookup, active_index=0)
        assert str(proxy["<jobindex>"].show.title.primary) == ""

    def test_proxy_iterable_for_lists(self):
        priority = {"data.<jobindex>.show": ["tmdb"]}
        resolver = DataResolver(priority)
        lookup = _make_lookup({
            (0, "tmdb"): {"show": {"genres": ["A", "B", "C"]}},
        })
        proxy = DataResolverProxy(resolver, lookup, active_index=0)
        assert list(proxy["<jobindex>"].show.genres) == ["A", "B", "C"]
        assert len(proxy["<jobindex>"].show.genres) == 3

    def test_proxy_bool(self):
        priority = {"data.<jobindex>.show": ["tmdb"]}
        resolver = DataResolver(priority)
        lookup_true = _make_lookup({(0, "tmdb"): {"show": {"x": "y"}}})
        lookup_false = _make_lookup({(0, "tmdb"): {"show": {}}})
        assert bool(DataResolverProxy(resolver, lookup_true, 0)["<jobindex>"].show.x) is True
        assert bool(DataResolverProxy(resolver, lookup_false, 0)["<jobindex>"].show.x) is False
