from __future__ import annotations

from article_ingest.storage import download_assets


class FakeResponse:
    def __init__(self, status_code: int, content: bytes, content_type: str) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response

    def get(self, url, timeout=15):
        return self._response


def test_download_assets_rewrites_markdown(tmp_path):
    markdown = "![img](https://example.com/image.png)"
    response = FakeResponse(200, b"img", "image/png")
    session = FakeSession(response)

    updated, assets = download_assets(
        tmp_path,
        source_slug="demo",
        item_key="https://example.com/post",
        version_index=1,
        markdown=markdown,
        base_url=None,
        session=session,
    )

    assert "assets/asset-1.png" in updated
    assert len(assets) == 1
    asset_path = assets[0]["local_path"]
    assert asset_path is not None
    assert (tmp_path / asset_path).exists()
