from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import storage


@pytest.fixture(autouse=True)
def _reset_memo():
    storage._uploads_bucket_ready = False
    yield
    storage._uploads_bucket_ready = False


def _mock_sb():
    sb = MagicMock()
    return sb


def test_create_upload_url_returns_signed_parts():
    sb = _mock_sb()
    sb.storage.from_.return_value.create_signed_upload_url.return_value = {
        "signed_url": "https://x.supabase.co/storage/v1/object/upload/sign/uploads/scenarii/abc.docx?token=T",
        "token": "T",
        "path": "scenarii/abc.docx",
    }
    with patch("storage.get_supabase", return_value=sb):
        out = storage.create_upload_url("scenarii", "Spec Vânzări.docx")
    assert out["signed_url"].startswith("https://")
    assert out["token"] == "T"
    assert out["storage_path"].startswith("scenarii/")
    assert out["storage_path"].endswith(".docx")
    sb.storage.from_.assert_called_with("uploads")


def test_create_upload_url_rejects_bad_tool_and_ext():
    with pytest.raises(ValueError):
        storage.create_upload_url("minuta", "a.docx")  # minuta nu foloseste fluxul
    with pytest.raises(ValueError):
        storage.create_upload_url("scenarii", "a.pdf")
    with pytest.raises(ValueError):
        storage.create_upload_url("scenarii", "a.xlsx")  # scenarii accepta doar .docx
    with pytest.raises(ValueError):
        storage.create_upload_url("mockup", "a.txt")


def test_ensure_uploads_bucket_creates_once():
    sb = _mock_sb()
    sb.storage.list_buckets.return_value = []
    with patch("storage.get_supabase", return_value=sb):
        storage.ensure_uploads_bucket()
        storage.ensure_uploads_bucket()  # a doua oara: memoizat, fara apel nou
    assert sb.storage.create_bucket.call_count == 1
    _, kwargs = sb.storage.create_bucket.call_args
    assert kwargs["options"]["public"] is False
    assert kwargs["options"]["file_size_limit"] == 52_428_800


def test_ensure_uploads_bucket_skips_if_exists():
    sb = _mock_sb()
    bucket = MagicMock()
    bucket.name = "uploads"
    sb.storage.list_buckets.return_value = [bucket]
    with patch("storage.get_supabase", return_value=sb):
        storage.ensure_uploads_bucket()
    sb.storage.create_bucket.assert_not_called()


def test_download_upload_writes_temp_and_removes_object():
    sb = _mock_sb()
    sb.storage.from_.return_value.download.return_value = b"PK-continut"
    with patch("storage.get_supabase", return_value=sb):
        path = storage.download_upload("scenarii/abc123.docx")
    try:
        assert path.suffix == ".docx"
        assert path.read_bytes() == b"PK-continut"
        sb.storage.from_.return_value.remove.assert_called_once_with(["scenarii/abc123.docx"])
    finally:
        path.unlink(missing_ok=True)


def test_download_upload_rejects_foreign_paths():
    with pytest.raises(ValueError):
        storage.download_upload("documents/altceva.docx")
    with pytest.raises(ValueError):
        storage.download_upload("../etc/passwd")


def test_ensure_uploads_bucket_cleans_old_orphans():
    from datetime import datetime, timedelta, timezone
    sb = _mock_sb()
    sb.storage.list_buckets.return_value = []
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    sb.storage.from_.return_value.list.side_effect = lambda folder: (
        [
            {"name": "vechi.docx", "created_at": old},
            {"name": "nou.docx", "created_at": fresh},
        ]
        if folder == "scenarii"
        else []
    )
    with patch("storage.get_supabase", return_value=sb):
        storage.ensure_uploads_bucket()
    sb.storage.from_.return_value.remove.assert_called_once_with(["scenarii/vechi.docx"])
