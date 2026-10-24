import csv
import io

import pytest
from fastapi.testclient import TestClient
from app import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "test.db"))


def example(**changes):
    return {"company": "Example Labs", "role": "Software Engineering Intern", "location": "London",
            "url": "https://example.com/jobs/1", "deadline": "2027-02-10", **changes}


def test_create_and_list(client):
    result = client.post("/api/applications", json=example())
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "Saved"
    assert len(client.get("/api/applications").json()) == 1


def test_duplicate_case_insensitive(client):
    client.post("/api/applications", json=example())
    assert client.post("/api/applications", json=example(company="EXAMPLE LABS")).status_code == 409


def test_reject_invalid_input(client):
    assert client.post("/api/applications", json=example(company=" ")).status_code == 422
    assert client.post("/api/applications", json=example(url="not-a-url")).status_code == 422


def test_patch_and_statistics(client):
    uid = client.post("/api/applications", json=example()).json()["id"]
    response = client.patch(f"/api/applications/{uid}", json={"status": "Interview", "notes": "Second round"})
    assert response.status_code == 200
    assert response.json()["notes"] == "Second round"
    assert client.get("/api/stats").json()["by_status"]["Interview"] == 1
    assert client.get("/api/applications?status=Interview").json()[0]["id"] == uid


def test_search(client):
    client.post("/api/applications", json=example())
    client.post("/api/applications", json=example(company="Acme", role="Data Engineering Intern"))
    assert len(client.get("/api/applications?q=data").json()) == 1
    assert len(client.get("/api/applications?q=Leeds").json()) == 0


def test_delete_and_not_found(client):
    uid = client.post("/api/applications", json=example()).json()["id"]
    assert client.delete(f"/api/applications/{uid}").status_code == 204
    assert client.delete(f"/api/applications/{uid}").status_code == 404
    assert client.patch("/api/applications/9999", json={"status": "Applied"}).status_code == 404


def test_csv_export(client):
    client.post("/api/applications", json=example(notes="=SUM(A1:A2)"))
    result = client.get("/api/export.csv")
    assert result.status_code == 200
    row = list(csv.DictReader(io.StringIO(result.text)))[0]
    assert row["company"] == "Example Labs"
    assert row["notes"].startswith("'=SUM")


def test_homepage_and_api_documentation(client):
    assert client.get("/").status_code == 200
    assert client.get("/openapi.json").status_code == 200
