from __future__ import annotations

from pyflow.models.platform import PlatformConfig


class TestTelemetryConfig:
    def test_telemetry_disabled_by_default(self):
        config = PlatformConfig()
        assert config.telemetry_enabled is False

    def test_telemetry_export_default(self):
        config = PlatformConfig()
        assert config.telemetry_export == "console"

    def test_telemetry_enabled_via_constructor(self):
        config = PlatformConfig(telemetry_enabled=True, telemetry_export="otlp")
        assert config.telemetry_enabled is True
        assert config.telemetry_export == "otlp"

    def test_telemetry_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("PYFLOW_TELEMETRY_ENABLED", "true")
        monkeypatch.setenv("PYFLOW_TELEMETRY_EXPORT", "gcp")
        config = PlatformConfig()
        assert config.telemetry_enabled is True
        assert config.telemetry_export == "gcp"
