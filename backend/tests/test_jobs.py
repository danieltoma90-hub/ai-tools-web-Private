import time
from pathlib import Path

import jobs


def test_job_lifecycle():
    job_id = jobs.create_job("ana@totalsoft.ro")
    job = jobs.get_job(job_id)
    assert job == {"status": "processing", "user_email": "ana@totalsoft.ro"}

    jobs.set_step(job_id, "module:1/3:Nomenclatoare")
    assert jobs.get_job(job_id)["step"] == "module:1/3:Nomenclatoare"

    jobs.finish(job_id, filename="a.xlsx", xlsx_b64="abc", ai_used=True)
    job = jobs.get_job(job_id)
    assert job["status"] == "done"
    assert job["filename"] == "a.xlsx"
    assert job["ai_used"] is True


def test_fail_sets_error():
    job_id = jobs.create_job("x@y.z")
    jobs.fail(job_id, "ceva a mers prost")
    assert jobs.get_job(job_id) == {"status": "error", "error": "ceva a mers prost"}


def test_get_unknown_job_returns_none():
    assert jobs.get_job("nu-exista") is None


def test_estimate_save_and_pop(tmp_path):
    f = tmp_path / "spec.docx"
    f.write_bytes(b"PK")
    eid = jobs.save_estimate(f, "spec.docx", {"est_tokens": 123, "fits_budget": True})
    est = jobs.pop_estimate(eid)
    assert est["filename"] == "spec.docx"
    assert est["est_tokens"] == 123
    assert est["file_path"] == str(f)
    # pop e destructiv
    assert jobs.pop_estimate(eid) is None


def test_estimate_expires_and_deletes_file(tmp_path, monkeypatch):
    f = tmp_path / "spec.docx"
    f.write_bytes(b"PK")
    eid = jobs.save_estimate(f, "spec.docx", {})
    # fortam expirarea
    jobs._estimates[eid]["created"] = time.monotonic() - jobs.ESTIMATE_TTL_S - 1
    assert jobs.pop_estimate(eid) is None
    assert not f.exists()
