from __future__ import annotations

import os
from unittest.mock import patch

from pyflow.platform.plugins import resolve_plugins, _PLUGIN_FACTORIES


class TestBigQueryPlugin:
    def test_bigquery_analytics_in_registry(self):
        """'bigquery_analytics' is a known plugin name."""
        assert "bigquery_analytics" in _PLUGIN_FACTORIES

    def test_bigquery_analytics_resolves_with_env(self, monkeypatch):
        """'bigquery_analytics' resolves when PYFLOW_BQ_* env vars are set."""
        monkeypatch.setenv("PYFLOW_BQ_PROJECT_ID", "test-project")
        monkeypatch.setenv("PYFLOW_BQ_DATASET_ID", "test-dataset")

        plugins = resolve_plugins(["bigquery_analytics"])
        assert len(plugins) == 1

    def test_bigquery_analytics_skipped_without_env(self):
        """'bigquery_analytics' is skipped when env vars are missing."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PYFLOW_BQ_PROJECT_ID", None)
            os.environ.pop("PYFLOW_BQ_DATASET_ID", None)
            plugins = resolve_plugins(["bigquery_analytics"])
            assert len(plugins) == 0
