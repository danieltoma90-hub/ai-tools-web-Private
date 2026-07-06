from unittest.mock import MagicMock, patch


async def test_health_pings_supabase_ok(client):
    sb = MagicMock()
    sb.storage.list_buckets.return_value = []
    with patch("main.get_supabase", return_value=sb):
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "supabase": "ok"}
    sb.storage.list_buckets.assert_called_once()


async def test_health_stays_ok_when_supabase_fails(client):
    with patch("main.get_supabase", side_effect=Exception("connection refused")):
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["supabase"].startswith("eroare")
