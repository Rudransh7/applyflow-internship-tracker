"""HTTP contracts and integration against isolated temporary databases."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from app import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.db", allowed_hosts=["testserver"]),
                    headers={"X-ApplyFlow-Request": "1"}) as session:
        yield session


def example(**changes):
    return {"company": "Example Labs", "role": "Software Engineering Intern", "location": "London",
            "url": "https://example.com/jobs/1", "deadline": "2027-02-10", **changes}


def test_create_list_and_get(client):
    response = client.post("/api/applications", json=example())
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["status"] == "Saved"
    assert client.get(response.headers["location"]).json() == item
    page = client.get("/api/applications").json()
    assert page["total"] == 1 and page["items"] == [item]


def test_duplicate_case_insensitive_and_patch_conflict(client):
    first = client.post("/api/applications", json=example()).json()
    assert client.post("/api/applications", json=example(company="EXAMPLE LABS")).status_code == 409
    other = client.post("/api/applications", json=example(company="Other Company")).json()
    assert client.patch(f"/api/applications/{other['id']}", json={"company": first["company"]}).status_code == 409
    assert client.get(f"/api/applications/{other['id']}").json()["company"] == "Other Company"


@pytest.mark.parametrize("change", [
    {"company": " "}, {"company": "x"}, {"company": "x" * 121}, {"role": "\t"},
    {"url": "not-a-url"}, {"url": "javascript:alert(1)"}, {"url": "https://me:secret@example.com"},
    {"deadline": "2027-02-30"}, {"status": "Finished"}, {"notes": "x" * 2001},
    {"unknown": "typo"}, {"notes": "has\x00nul"}, {"company": None},
])
def test_reject_invalid_input(client, change):
    assert client.post("/api/applications", json=example(**change)).status_code == 422
    assert client.get("/api/stats").json()["total"] == 0


@pytest.mark.parametrize("patch", [{}, {"company": None}, {"notes": None}, {"status": None},
                                  {"location": None}, {"typo": "oops"}, {"url": "ftp://example.com"}])
def test_reject_invalid_patch(client, patch):
    uid = client.post("/api/applications", json=example()).json()["id"]
    assert client.patch(f"/api/applications/{uid}", json=patch).status_code == 422


def test_patch_clear_fields_and_statistics(client):
    item = client.post("/api/applications", json=example()).json()
    response = client.patch(f"/api/applications/{item['id']}", json={"status": "Interview", "notes": "Second round", "url": None, "deadline": None})
    assert response.status_code == 200
    result = response.json()
    assert result["notes"] == "Second round" and result["deadline"] is None and result["url"] is None
    assert result["created_at"] == item["created_at"]
    assert result["updated_at"] >= item["updated_at"]
    assert client.get("/api/stats").json()["by_status"]["Interview"] == 1
    assert client.get("/api/applications?status=Interview").json()["items"][0]["id"] == item["id"]


def test_search_filter_pagination_and_literal_wildcards(client):
    client.post("/api/applications", json=example(company="100% Labs"))
    client.post("/api/applications", json=example(company="Acme", role="Data Engineering Intern", status="Applied"))
    assert client.get("/api/applications?q=data&status=Applied").json()["total"] == 1
    assert client.get("/api/applications?q=data&status=Saved").json()["total"] == 0
    assert client.get("/api/applications", params={"q": "%"}).json()["total"] == 1
    assert client.get("/api/applications", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    first = client.get("/api/applications?limit=1").json()
    second = client.get("/api/applications?limit=1&offset=1").json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "status=invalid", "deadline=invalid"])
def test_invalid_query(client, query):
    assert client.get(f"/api/applications?{query}").status_code == 422


def test_delete_and_not_found(client):
    uid = client.post("/api/applications", json=example()).json()["id"]
    assert client.delete(f"/api/applications/{uid}").status_code == 204
    assert client.delete(f"/api/applications/{uid}").status_code == 404
    assert client.get(f"/api/applications/{uid}").status_code == 404
    assert client.patch("/api/applications/9999", json={"status": "Applied"}).status_code == 404


@pytest.mark.parametrize("notes", ["=SUM(A1:A2)", "+cmd", "-cmd", "@SUM(A1)", "  =1+1", "\t=1"])
def test_csv_export_escapes_formulas(client, notes):
    client.post("/api/applications", json=example(notes=notes))
    response = client.get("/api/export.csv")
    assert response.status_code == 200
    row = list(csv.DictReader(io.StringIO(response.text)))[0]
    assert row["company"] == "Example Labs"
    assert row["notes"].startswith("'")


def upload(client, text):
    return client.post("/api/import.csv", content=text, headers={"Content-Type": "text/csv"})


def test_csv_import_unicode_quotes_and_defaults(client):
    response = upload(client, '\ufeffcompany,role,notes\r\n"Example, Ltd",Software Intern,"Hello\nworld"\r\nCafé Labs,Intern,你好\r\n'.encode())
    assert response.status_code == 201, response.text
    assert response.json()["imported"] == 2
    items = client.get("/api/applications").json()["items"]
    assert all(item["status"] == "Saved" for item in items)
    assert {item["notes"] for item in items} == {"Hello\nworld", "你好"}


def test_csv_validation_is_all_or_nothing(client):
    response = upload(client, b"company,role,deadline\nValid Labs,Intern,2027-01-01\nBad Labs,Intern,not-a-date\n")
    assert response.status_code == 422
    assert response.json()["errors"][0]["row"] == 3
    assert client.get("/api/stats").json()["total"] == 0


def test_csv_conflict_rolls_back_earlier_rows(client):
    client.post("/api/applications", json=example())
    response = upload(client, b"company,role\nNew Labs,Intern\nExample Labs,Software Engineering Intern\n")
    assert response.status_code == 409
    assert client.get("/api/stats").json()["total"] == 1


@pytest.mark.parametrize("content", [b"", b"company,role\n", b"company\nLab\n", b"company,role,company\nLab,Intern,Lab\n",
    b"company,role,unknown\nLab,Intern,x\n", b"company,role\nLab,Intern,extra\n", b'company,role\n"unterminated,Intern', b"\xff\xfe"])
def test_bad_csv(client, content):
    assert upload(client, content).status_code == 422
    assert client.get("/api/stats").json()["total"] == 0


def test_csv_limits_and_content_type(client):
    assert upload(client, b"x" * 1_000_001).status_code == 413
    assert upload(client, ("company,role\n" + "Lab,Intern\n" * 501).encode()).status_code == 422
    assert client.post("/api/import.csv", json={}).status_code == 415


def test_homepage_security_headers_and_documentation(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/health").json() == {"status": "ok"}


def test_cross_origin_and_missing_mutation_header(client):
    assert client.post("/api/applications", json=example(), headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/applications", json=example(), headers={"X-ApplyFlow-Request": ""}).status_code == 403
    assert client.post("/api/applications", json=example(), headers={"Origin": "http://testserver"}).status_code == 201
    assert client.get("/api/applications", headers={"Host": "evil.example"}).status_code == 400
