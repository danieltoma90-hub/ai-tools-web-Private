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


def test_job_terminat_dispare_dupa_ttl():
    """Documentul in base64 nu are voie sa ramana in memorie la nesfarsit."""
    job_id = jobs.create_job("ana@totalsoft.ro")
    jobs.finish(job_id, filename="a.docx", docx_b64="x" * 1000)
    assert jobs.get_job(job_id) is not None

    jobs._job_meta[job_id]["terminat"] = time.monotonic() - jobs.JOB_TTL_S - 1
    assert jobs.get_job(job_id) is None
    assert job_id not in jobs._job_meta


def test_job_in_lucru_nu_e_sters_de_ttl_ul_de_livrare():
    """Minuta free poate rula minute bune — job-ul ei nu se sterge sub picioare."""
    job_id = jobs.create_job("ana@totalsoft.ro")
    jobs._job_meta[job_id]["creat"] = time.monotonic() - jobs.JOB_TTL_S - 60
    assert jobs.get_job(job_id) is not None
    assert jobs.get_job(job_id)["status"] == "processing"


def test_job_agatat_dispare_dupa_durata_maxima():
    job_id = jobs.create_job("ana@totalsoft.ro")
    jobs._job_meta[job_id]["creat"] = time.monotonic() - jobs.JOB_MAX_LIFETIME_S - 1
    assert jobs.get_job(job_id) is None


def test_curatenia_nu_atinge_job_urile_vii():
    vechi = jobs.create_job("x@y.z")
    jobs.finish(vechi, filename="vechi.docx")
    jobs._job_meta[vechi]["terminat"] = time.monotonic() - jobs.JOB_TTL_S - 1

    nou = jobs.create_job("x@y.z")  # create_job declanseaza curatenia
    assert jobs.get_job(vechi) is None
    assert jobs.get_job(nou) is not None


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
