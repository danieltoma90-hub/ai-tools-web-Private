import pytest
from unittest.mock import MagicMock
from storage import upload_file, list_files
from pathlib import Path


@pytest.fixture
def mock_supabase(monkeypatch):
    mock_sb = MagicMock()
    monkeypatch.setattr("storage.get_supabase", lambda: mock_sb)
    return mock_sb


def test_upload_file_returns_public_path(mock_supabase, tmp_path):
    docx = tmp_path / "test.docx"
    docx.write_bytes(b"fake docx content")

    mock_supabase.storage.from_.return_value.upload.return_value = MagicMock()

    result = upload_file(docx, tool="minuta", filename="Minuta_Test.docx", user_email="user@test.com")

    mock_supabase.storage.from_.assert_called_with("documents")
    assert result == "minuta/user@test.com/Minuta_Test.docx"


def test_list_files_returns_sorted_list(mock_supabase):
    mock_supabase.storage.from_.return_value.list.return_value = [
        {"name": "Minuta_B.docx", "created_at": "2026-06-25T14:00:00", "metadata": {"size": 12000}},
        {"name": "Minuta_A.docx", "created_at": "2026-06-25T10:00:00", "metadata": {"size": 8000}},
    ]

    result = list_files(tool="minuta")

    assert len(result) == 2
    assert result[0]["name"] == "Minuta_B.docx"


def test_listarea_se_refoloseste_si_se_goleste_la_upload(mock_supabase, tmp_path):
    """Pagina Acasă cere listarea la 30 de secunde; Supabase e întrebat o singură dată
    până la următorul document încărcat."""
    import storage

    lista = mock_supabase.storage.from_.return_value.list
    list_files(tool="minuta")
    apeluri = lista.call_count
    list_files(tool="minuta")
    assert lista.call_count == apeluri  # din cache

    docx = tmp_path / "a.docx"
    docx.write_bytes(b"PK")
    upload_file(docx, tool="minuta", filename="a.docx", user_email="u@x.ro")
    list_files(tool="minuta")
    assert lista.call_count > apeluri  # documentul nou se vede imediat


def test_listarea_intoarce_copii(mock_supabase):
    mock_supabase.storage.from_.return_value.list.return_value = [
        {"name": "A.docx", "created_at": "2026-06-25T10:00:00", "metadata": {"size": 8000}},
    ]
    prima = list_files(tool="minuta")
    assert prima
    for f in prima:
        f["download_url"] = "modificat"
    assert all("download_url" not in f for f in list_files(tool="minuta"))
