import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("GCS_CREDENTIALS_PATH", "/tmp/dummy.json")
os.environ.setdefault("GCS_BUCKET_NAME", "dummy")

with mock.patch("google.cloud.storage.Client.from_service_account_json") as m:
    dummy_client = mock.Mock()
    dummy_client.get_bucket.return_value = mock.Mock()
    m.return_value = dummy_client
    from api.routes.video_routes import validate_rtsp_url


@pytest.mark.parametrize("url", [
    "rtsp://example.com/live/stream",
    "rtsp://example.com:554/live",
])
def test_validate_rtsp_url_domain(url):
    assert validate_rtsp_url(url)


@pytest.mark.parametrize("url", [
    "rtsp://192.168.1.1/stream",
    "rtsp://user:pass@192.168.1.1:8554/stream",
])
def test_validate_rtsp_url_ip(url):
    assert validate_rtsp_url(url)


@pytest.mark.parametrize("url", [
    "http://example.com/stream",
    "rtsp://",
    "rtsp://invalid domain/stream",
])
def test_validate_rtsp_url_invalid(url):
    assert not validate_rtsp_url(url)
