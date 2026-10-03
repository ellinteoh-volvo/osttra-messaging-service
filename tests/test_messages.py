
import pytest

import app as app_module
import db

# Each test gets its own temporary database so tests do not affect real data or each other.
@pytest.fixture
def client(tmp_path, monkeypatch):
    # Create a temporary database path
    test_db = tmp_path / "test_messages.db"

    # Redirect our application to the test database
    monkeypatch.setattr(db, "DB_PATH", test_db)

    # Create the messages table
    db.init_db()

    # Return a Flask test client
    return app_module.app.test_client()

def test_create_and_retrieve_message(client):
    # Create a message
    response = client.post(
        "/messages",
        json={
            "recipient": "alice",
            "text": "My automated test message"
        }
    )

    # Verify successful creation
    assert response.status_code == 201

    message = response.get_json()

    assert message["recipient"] == "alice"
    assert message["text"] == "My automated test message"
    assert message["unread"] is True
    assert isinstance(message["id"], int)
    assert "created_at" in message
    assert isinstance(message["created_at"], str)
    assert message["created_at"]

    # Retrieve the saved message
    response = client.get("/messages?recipient=alice")

    assert response.status_code == 200

    messages = response.get_json()

    assert len(messages) == 1
    assert messages[0]["id"] == message["id"]
    assert messages[0]["text"] == "My automated test message"



def test_fetch_unread_messages_marks_them_as_read(client):
    # Create a new unread message
    create_response = client.post(
        "/messages",
        json={
            "recipient": "alice",
            "text": "Unread message"
        }
    )

    assert create_response.status_code == 201

    # Fetch unread messages
    fetch_response = client.post(
        "/messages/unread/fetch?recipient=alice"
    )

    assert fetch_response.status_code == 200

    unread_messages = fetch_response.get_json()

    assert len(unread_messages) == 1
    assert unread_messages[0]["text"] == "Unread message"
    assert unread_messages[0]["unread"] is False

    # Fetch unread messages again
    second_fetch_response = client.post(
        "/messages/unread/fetch?recipient=alice"
    )

    assert second_fetch_response.status_code == 200
    assert second_fetch_response.get_json() == []

    # The message should still exist in normal retrieval
    all_messages_response = client.get(
        "/messages?recipient=alice"
    )

    assert all_messages_response.status_code == 200

    all_messages = all_messages_response.get_json()

    assert len(all_messages) == 1
    assert all_messages[0]["text"] == "Unread message"
    assert all_messages[0]["unread"] is False



def test_delete_single_message(client):
    # Create a message
    create_response = client.post(
        "/messages",
        json={
            "recipient": "alice",
            "text": "Delete this message"
        }
    )

    assert create_response.status_code == 201

    message_id = create_response.get_json()["id"]

    # Delete the message
    delete_response = client.delete(
        f"/messages/{message_id}"
    )

    assert delete_response.status_code == 204

    # Verify that the message is gone
    get_response = client.get(
        "/messages?recipient=alice"
    )

    assert get_response.status_code == 200
    assert get_response.get_json() == []

    # Deleting the same message again should return 404
    second_delete_response = client.delete(
        f"/messages/{message_id}"
    )

    assert second_delete_response.status_code == 404
    assert second_delete_response.get_json() == {
        "error": "Message not found"
    }



def test_batch_delete(client):
    # Create two messages
    first_response = client.post(
        "/messages",
        json={
            "recipient": "alice",
            "text": "First batch message"
        }
    )

    second_response = client.post(
        "/messages",
        json={
            "recipient": "alice",
            "text": "Second batch message"
        }
    )

    first_id = first_response.get_json()["id"]
    second_id = second_response.get_json()["id"]

    # Successfully delete both messages
    delete_response = client.delete(
        "/messages",
        json={
            "ids": [first_id, second_id]
        }
    )

    assert delete_response.status_code == 200
    assert delete_response.get_json() == {
        "deleted_count": 2
    }

    # Verify both are gone
    get_response = client.get(
        "/messages?recipient=alice"
    )

    assert get_response.status_code == 200
    assert get_response.get_json() == []



def test_batch_delete_rolls_back_if_one_message_is_missing(client):
    # Create one real message
    create_response = client.post(
        "/messages",
        json={
            "recipient": "alice",
            "text": "This message must survive"
        }
    )

    assert create_response.status_code == 201

    existing_id = create_response.get_json()["id"]
    missing_id = 999999999

    # Attempt to delete one existing and one missing message
    delete_response = client.delete(
        "/messages",
        json={
            "ids": [existing_id, missing_id]
        }
    )

    assert delete_response.status_code == 404
    assert delete_response.get_json() == {
        "error": "One or more messages not found"
    }

    # Verify that the existing message was NOT deleted
    get_response = client.get(
        "/messages?recipient=alice"
    )

    assert get_response.status_code == 200

    messages = get_response.get_json()

    assert len(messages) == 1
    assert messages[0]["id"] == existing_id
    assert messages[0]["text"] == "This message must survive"



def test_messages_are_ordered_and_paginated(client):
    # Create three messages in order
    for text in [
        "First message",
        "Second message",
        "Third message"
    ]:
        response = client.post(
            "/messages",
            json={
                "recipient": "alice",
                "text": text
            }
        )

        assert response.status_code == 201

    # Retrieve messages at indexes 1 and 2
    response = client.get(
        "/messages?recipient=alice&start=1&stop=3"
    )

    assert response.status_code == 200

    messages = response.get_json()

    assert len(messages) == 2
    assert messages[0]["text"] == "Second message"
    assert messages[1]["text"] == "Third message"


def test_start_only_pagination(client):
    for text in ["First", "Second", "Third"]:
        client.post(
            "/messages",
            json={"recipient": "alice", "text": text}
        )

    response = client.get(
        "/messages?recipient=alice&start=1"
    )

    assert response.status_code == 200

    messages = response.get_json()

    assert [m["text"] for m in messages] == [
        "Second",
        "Third"
    ]


def test_stop_only_pagination(client):
    for text in ["First", "Second", "Third"]:
        client.post(
            "/messages",
            json={"recipient": "alice", "text": text}
        )

    response = client.get(
        "/messages?recipient=alice&stop=2"
    )

    assert response.status_code == 200

    messages = response.get_json()

    assert [m["text"] for m in messages] == [
        "First",
        "Second"
    ]


def test_invalid_pagination_parameters(client):
    negative_start = client.get(
        "/messages?recipient=alice&start=-1"
    )

    assert negative_start.status_code == 400
    assert negative_start.get_json() == {
        "error": "start must be a non-negative integer"
    }

    non_numeric_stop = client.get(
        "/messages?recipient=alice&stop=abc"
    )

    assert non_numeric_stop.status_code == 400
    assert non_numeric_stop.get_json() == {
        "error": "stop must be a non-negative integer"
    }

    invalid_range = client.get(
        "/messages?recipient=alice&start=5&stop=2"
    )

    assert invalid_range.status_code == 400
    assert invalid_range.get_json() == {
        "error": "stop must be greater than or equal to start"
    }



def test_create_message_requires_recipient(client):
    response = client.post(
        "/messages",
        json={
            "text": "Hello"
        }
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "A recipient is required"
    }


def test_create_message_requires_text(client):
    response = client.post(
        "/messages",
        json={
            "recipient": "alice"
        }
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Message text is required"
    }


def test_create_message_requires_json_object(client):
    response = client.post(
        "/messages",
        data="this is not json",
        content_type="text/plain"
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "A JSON object is required"
    }


def test_get_messages_requires_recipient(client):
    response = client.get("/messages")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "A recipient is required"
    }


def test_batch_delete_rejects_empty_ids(client):
    response = client.delete(
        "/messages",
        json={
            "ids": []
        }
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "A non-empty list of IDs is required"
    }


def test_batch_delete_rejects_invalid_ids(client):
    response = client.delete(
        "/messages",
        json={
            "ids": [1, -2]
        }
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "IDs must be positive integers"
    }


def test_batch_delete_rejects_duplicate_ids(client):
    response = client.delete(
        "/messages",
        json={
            "ids": [1, 1]
        }
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Duplicate IDs are not allowed"
    }