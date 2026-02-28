from __future__ import annotations

from pyflow.models.workflow import McpServerConfig, RuntimeConfig


class TestMcpServerConfig:
    def test_sse_config(self):
        config = McpServerConfig(uri="http://localhost:3000/sse", transport="sse")
        assert config.uri == "http://localhost:3000/sse"
        assert config.transport == "sse"

    def test_stdio_config(self):
        config = McpServerConfig(
            command="npx", args=["-y", "@mcp/server-filesystem", "/tmp"], transport="stdio"
        )
        assert config.command == "npx"
        assert config.transport == "stdio"

    def test_runtime_config_with_mcp(self):
        runtime = RuntimeConfig(
            mcp_servers=[McpServerConfig(uri="http://localhost:3000/sse", transport="sse")]
        )
        assert len(runtime.mcp_servers) == 1

    def test_runtime_config_default_empty(self):
        runtime = RuntimeConfig()
        assert runtime.mcp_servers == []


class TestMcpToolResolution:
    def test_mcp_config_to_params_sse(self):
        from pyflow.platform.hydration.hydrator import _mcp_config_to_params
        from google.adk.tools.mcp_tool.mcp_toolset import SseConnectionParams

        config = McpServerConfig(uri="http://localhost:3000/sse", transport="sse")
        params = _mcp_config_to_params(config)
        assert isinstance(params, SseConnectionParams)

    def test_mcp_config_to_params_stdio(self):
        from pyflow.platform.hydration.hydrator import _mcp_config_to_params
        from mcp import StdioServerParameters

        config = McpServerConfig(command="npx", args=["-y", "server"], transport="stdio")
        params = _mcp_config_to_params(config)
        assert isinstance(params, StdioServerParameters)
