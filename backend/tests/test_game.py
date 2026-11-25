from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest

from conftest import TEST_TOKEN, signed_data
from dreamteam.auth import InvalidCredentials, TelegramAuth


def new_lobby(client):
    response = client.post("/api/lobbies")
    assert response.status_code == 200, response.text
    lobby = response.json()
    code = parse_qs(urlparse(lobby["inviteUrl"]).query)["startapp"][0]
    return lobby["id"], code


def enter(client, code):
    return client.post("/api/lobbies/join", json={"code": code})


def test_auth_rejects_modified_expired_and_ambiguous_payloads():
    auth = TelegramAuth(TEST_TOKEN)
    data = signed_data(123, "Player")
    assert auth.verify_init_data(data).id == 123
    for invalid in (data.replace("Player", "Another"), data + "&auth_date=1", signed_data(123, "Player", offset=-901)):
        with pytest.raises(InvalidCredentials):
            auth.verify_init_data(invalid)
    token = auth.issue_session(123)
    assert auth.verify_session(token) == 123
    with pytest.raises(InvalidCredentials):
        auth.verify_session(token.replace("123.", "124.", 1))


def test_profile_and_tactics_survive_new_session(client_factory, player, database):
    anonymous = client_factory()
    assert anonymous.get("/api/me").status_code == 401
    assert anonymous.post("/api/session", json={"initData": "hash=invalid"}).status_code == 401

    first = player(100, "Sam")
    profile = first.get("/api/me").json()
    assert profile["displayName"] == "Sam"
    assert [(card["slot"], card["role"], card["power"]) for card in profile["team"]] == [
        (1, "IGL", 50), (2, "AWP", 50), (3, "Entry", 50), (4, "Support", 50), (5, "Lurker", 50),
    ]
    selections = [
        {"map": "mirage", "side": "T", "preset": "fast"},
        {"map": "mirage", "side": "CT", "preset": "hold"},
    ]
    for selection in selections:
        assert first.put("/api/tactics", json=selection).status_code == 200
    assert first.put("/api/tactics", json={**selections[0], "preset": "invalid"}).status_code == 422

    next_session = player(100, "Sam")
    assert next_session.get("/api/me").json()["team"] == profile["team"]
    assert next_session.get("/api/tactics").json() == list(reversed(selections))
    assert player(200, "Guest").get("/api/tactics").json() == []
    with psycopg.connect(database) as db:
        assert db.execute("SELECT count(*) FROM accounts").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM team_players WHERE telegram_id = 100").fetchone()[0] == 5


def test_concurrent_first_login_keeps_one_team(player, database):
    with ThreadPoolExecutor(max_workers=2) as pool:
        clients = list(pool.map(lambda _: player(42, "Player"), range(2)))

    teams = [client.get("/api/me").json()["team"] for client in clients]
    assert teams[0] == teams[1]
    assert len(teams[0]) == 5
    with psycopg.connect(database) as db:
        assert db.execute("SELECT count(*) FROM accounts WHERE telegram_id = 42").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM team_players WHERE telegram_id = 42").fetchone()[0] == 5


def test_lobby_is_private_and_readiness_recovers_after_login(player):
    host, guest, stranger = player(1, "Host"), player(2, "Guest"), player(3, "Stranger")
    lobby_id, code = new_lobby(host)
    endpoint = f"/api/lobbies/{lobby_id}"

    assert new_lobby(host) == (lobby_id, code)
    assert enter(stranger, code[:-1] + ("a" if code[-1] != "a" else "b")).status_code == 404
    assert enter(host, code).status_code == 409
    assert stranger.get(endpoint).status_code == 404
    assert stranger.put(endpoint + "/ready", json={"ready": True}).status_code == 404
    assert enter(guest, code).status_code == 200
    assert enter(guest, code).status_code == 200
    assert enter(stranger, code).status_code == 409
    assert guest.delete(endpoint).status_code == 403

    assert host.put(endpoint + "/ready", json={"ready": True}).json()["status"] == "waiting"
    assert guest.put(endpoint + "/ready", json={"ready": True}).json()["status"] == "ready"
    assert guest.put(endpoint + "/ready", json={"ready": True}).json()["status"] == "ready"
    returning = player(2, "Guest")
    assert returning.get("/api/me").json()["activeLobby"] == lobby_id
    assert returning.get(endpoint).json()["status"] == "ready"
    assert "inviteUrl" not in returning.get(endpoint).json()

    assert host.delete(endpoint).json()["status"] == "cancelled"
    assert enter(guest, code).status_code == 410
    assert returning.get("/api/me").json()["activeLobby"] is None


def test_expired_lobby_releases_active_slot(player, database):
    host, guest = player(1, "Host"), player(2, "Guest")
    old_id, code = new_lobby(host)
    with psycopg.connect(database) as db:
        db.execute("UPDATE lobbies SET expires_at = clock_timestamp() WHERE id = %s", (old_id,))
    assert enter(guest, code).status_code == 410
    assert host.get(f"/api/lobbies/{old_id}").json()["status"] == "expired"
    assert new_lobby(host)[0] != old_id


def test_concurrent_join_never_adds_a_third_participant(player):
    host, first, second = player(1, "Host"), player(2, "First"), player(3, "Second")
    lobby_id, code = new_lobby(host)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda client: enter(client, code).status_code, [first, second]))
    assert sorted(results) == [200, 409]
    assert len(host.get(f"/api/lobbies/{lobby_id}").json()["participants"]) == 2


def test_concurrent_readiness_creates_one_private_series(player, database):
    host, guest, outsider = player(1, "Host"), player(2, "Guest"), player(3, "Outsider")
    lobby_id, code = new_lobby(host)
    endpoint = f"/api/lobbies/{lobby_id}"
    assert host.put(endpoint + "/ready", json={"ready": True}).json()["series"] is None
    assert host.put(endpoint + "/ready", json={"ready": False}).json()["series"] is None
    assert enter(guest, code).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda client: client.put(endpoint + "/ready", json={"ready": True}), [host, guest]))
    assert [r.status_code for r in responses] == [200, 200]
    assert sum(r.json()["series"] is not None for r in responses) == 1

    series = host.get(endpoint).json()["series"]
    assert series["phase"] == "awaiting_veto"
    assert guest.put(endpoint + "/ready", json={"ready": True}).json()["series"] == series
    assert host.put(endpoint + "/ready", json={"ready": False}).status_code == 409
    series_endpoint = f"/api/series/{series['id']}"
    assert outsider.get(series_endpoint).status_code == 404

    with psycopg.connect(database) as db:
        assert db.execute("SELECT count(*) FROM series WHERE lobby_id = %s", (lobby_id,)).fetchone()[0] == 1
        db.execute("UPDATE lobbies SET expires_at = clock_timestamp() WHERE id = %s", (lobby_id,))

    returning = player(2, "Guest")
    assert returning.get("/api/me").json()["activeLobby"] == lobby_id
    assert returning.get(series_endpoint).json() == series
    assert enter(returning, code).json()["series"] == series
    assert outsider.post("/api/lobbies").status_code == 200
    assert host.get(endpoint).json()["series"] == series

    assert host.delete(endpoint).json()["series"]["phase"] == "cancelled"
    assert guest.get(series_endpoint).json()["phase"] == "cancelled"
    assert guest.put(endpoint + "/ready", json={"ready": True}).status_code == 410


def test_cancelled_lobby_cannot_start_series(player, database):
    host, guest = player(1, "Host"), player(2, "Guest")
    lobby_id, code = new_lobby(host)
    endpoint = f"/api/lobbies/{lobby_id}"
    assert enter(guest, code).status_code == 200
    assert host.put(endpoint + "/ready", json={"ready": True}).status_code == 200
    assert host.delete(endpoint).json()["status"] == "cancelled"
    assert guest.put(endpoint + "/ready", json={"ready": True}).status_code == 410
    with psycopg.connect(database) as db:
        assert db.execute("SELECT count(*) FROM series WHERE lobby_id = %s", (lobby_id,)).fetchone()[0] == 0


def test_concurrent_cancellation_and_readiness_end_without_an_active_series(player, database):
    host, guest = player(1, "Host"), player(2, "Guest")
    lobby_id, code = new_lobby(host)
    endpoint = f"/api/lobbies/{lobby_id}"
    assert enter(guest, code).status_code == 200
    assert host.put(endpoint + "/ready", json={"ready": True}).json()["series"] is None
    start = Barrier(2, timeout=10)

    def cancel():
        start.wait()
        return host.delete(endpoint)

    def ready():
        start.wait()
        return guest.put(endpoint + "/ready", json={"ready": True})

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel_request = pool.submit(cancel)
        ready_request = pool.submit(ready)
        cancelled = cancel_request.result(timeout=15)
        readied = ready_request.result(timeout=15)

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert readied.status_code in (200, 410)
    assert guest.get(endpoint).json()["status"] == "cancelled"
    assert host.get("/api/me").json()["activeLobby"] is None
    assert guest.get("/api/me").json()["activeLobby"] is None
    assert guest.put(endpoint + "/ready", json={"ready": True}).status_code == 410

    with psycopg.connect(database) as db:
        phases = db.execute("SELECT phase FROM series WHERE lobby_id = %s", (lobby_id,)).fetchall()
        expected = [("cancelled",)] if readied.status_code == 200 else []
        assert phases == expected
