"""S41: PluginServices no longer exposes the S40 deprecated stubs."""

from archiverr.core.services.plugin_services import PluginServices


DELETED = (
    "update_job",
    "update_plugin",
    "get_plugin_data",
    "get_run",
    "get_config",
    "get_current_job",
    "get_all_jobs",
    "get_current_plugins",
    "get_all_plugins",
    "mode",
    "current_job_id",
    "current_plugin_name",
    "run_id",
    "_warn_deprecated",
)


def test_s41_hard_deleted_plugin_service_stubs():
    for name in DELETED:
        assert not hasattr(PluginServices, name), name


def test_s41_canonical_surface_remains():
    for name in ("create_job", "read_state", "update_state", "jobid", "get_runtime_config"):
        assert hasattr(PluginServices, name), name
