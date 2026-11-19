import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from dreamteam.api import create_app
from dreamteam.migrate import migrate

TEST_TOKEN = "test-fixture"


def signed_data(user_id, name, *, offset=0):
    fields = {
        "user": json.dumps({"id": user_id, "first_name": name}),
        "auth_date": str(int(time.time()) + offset),
        "query_id": "fixture",
    }
    secret = hmac.new(b"WebAppData", TEST_TOKEN.encode(), hashlib.sha256).digest()
    data = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    fields["hash"] = hmac.new(secret, data.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.fixture
def database():
    url = os.getenv("DREAMTEAM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set DREAMTEAM_TEST_DATABASE_URL to run PostgreSQL integration tests")
    schema_name = f"test_{uuid4().hex}"
    schema = sql.Identifier(schema_name)
    with psycopg.connect(url, autocommit=True) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        try:
            connection = make_conninfo(url, options=f"-c search_path={schema_name}")
            with psycopg.connect(connection) as isolated:
                migrate(isolated)
                migrate(isolated)
            yield connection
        finally:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))


@pytest.fixture
def client_factory(database):
    app = create_app(database, TEST_TOKEN, "dreamteam_test_bot", False)
    return lambda: TestClient(app)


@pytest.fixture
def player(client_factory):
    def login(user_id, name):
        client = client_factory()
        response = client.post("/api/session", json={"initData": signed_data(user_id, name)})
        assert response.status_code == 200, response.text
        return client

    return login
