import json
import os
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:5000"
).rstrip("/")


def api_request(method, endpoint, payload=None, token=None):
    headers = {}
    body = None

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(
        url=f"{BASE_URL}{endpoint}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
            raw_body = response.read()
    except HTTPError as error:
        status = error.code
        raw_body = error.read()

    response_data = (
        json.loads(raw_body.decode("utf-8"))
        if raw_body
        else None
    )

    return status, response_data


def event_payload(is_public=True):
    return {
        "title": f"MSIT Test Event {uuid.uuid4().hex[:8]}",
        "description": "Automated integration test event",
        "date": "2035-06-15T18:00:00",
        "location": "Berlin",
        "capacity": 50,
        "is_public": is_public,
        "requires_admin": False,
    }


@pytest.fixture(scope="module")
def registered_user():
    username = f"msit_{uuid.uuid4().hex[:16]}"
    password = "SecureTestPassword123!"

    status, response = api_request(
        "POST",
        "/api/auth/register",
        {
            "username": username,
            "password": password,
        },
    )

    assert status == 201, response

    return {
        "username": username,
        "password": password,
        "response": response,
    }


@pytest.fixture(scope="module")
def authenticated_user(registered_user):
    status, response = api_request(
        "POST",
        "/api/auth/login",
        {
            "username": registered_user["username"],
            "password": registered_user["password"],
        },
    )

    assert status == 200, response
    assert isinstance(response.get("access_token"), str)

    return {
        "username": registered_user["username"],
        "token": response["access_token"],
        "response": response,
    }


@pytest.fixture(scope="module")
def public_event(authenticated_user):
    payload = event_payload(is_public=True)

    status, response = api_request(
        "POST",
        "/api/events",
        payload,
        authenticated_user["token"],
    )

    assert status == 201, response

    return {
        "payload": payload,
        "response": response,
    }


@pytest.fixture(scope="module")
def protected_event(authenticated_user):
    payload = event_payload(is_public=False)

    status, response = api_request(
        "POST",
        "/api/events",
        payload,
        authenticated_user["token"],
    )

    assert status == 201, response

    return response


def test_health_check():
    status, response = api_request(
        "GET",
        "/api/health",
    )

    assert status == 200
    assert response["status"] == "healthy"


def test_user_registration(registered_user):
    response = registered_user["response"]

    assert response["message"] == "User created successfully"
    assert response["user"]["username"] == registered_user["username"]
    assert isinstance(response["user"]["id"], int)
    assert "password" not in response["user"]
    assert "password_hash" not in response["user"]


def test_user_login(authenticated_user):
    response = authenticated_user["response"]
    token = response["access_token"]

    assert isinstance(token, str)
    assert len(token.split(".")) == 3
    assert response["user"]["username"] == authenticated_user["username"]


def test_authenticated_event_creation(public_event):
    payload = public_event["payload"]
    response = public_event["response"]

    assert isinstance(response["id"], int)
    assert response["title"] == payload["title"]
    assert response["is_public"] is True
    assert response["capacity"] == payload["capacity"]


def test_public_event_rsvp(public_event):
    event_id = public_event["response"]["id"]

    status, response = api_request(
        "POST",
        f"/api/rsvps/event/{event_id}",
        {"attending": True},
    )

    assert status == 201, response
    assert response["event_id"] == event_id
    assert response["attending"] is True
    assert isinstance(response["id"], int)


def test_duplicate_username(registered_user):
    status, response = api_request(
        "POST",
        "/api/auth/register",
        {
            "username": registered_user["username"],
            "password": registered_user["password"],
        },
    )

    assert status == 400
    assert response["error"] == "Username already exists"


def test_event_creation_without_token():
    status, response = api_request(
        "POST",
        "/api/events",
        event_payload(),
    )

    assert status == 401
    assert response["msg"] == "Missing Authorization Header"


def test_protected_event_rsvp_without_token(protected_event):
    event_id = protected_event["id"]

    status, response = api_request(
        "POST",
        f"/api/rsvps/event/{event_id}",
        {"attending": True},
    )

    assert status == 401
    assert response["error"] == "Authentication required for this event"
