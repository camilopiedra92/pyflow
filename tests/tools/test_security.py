from __future__ import annotations

import pytest

from pyflow.tools.security import is_private_url


class TestIsPrivateUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/api",
            "http://localhost/api",
            "http://10.0.0.1/api",
            "http://172.16.0.1/api",
            "http://192.168.1.1/api",
            "http://169.254.169.254/latest/meta-data",
            "http://[::1]/api",
            "http://0.0.0.0/api",
        ],
    )
    def test_blocks_private_urls(self, url: str):
        assert is_private_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://api.example.com/data",
            "https://8.8.8.8/dns",
            "https://httpbin.org/get",
        ],
    )
    def test_allows_public_urls(self, url: str):
        assert is_private_url(url) is False
