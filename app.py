
from flask import Flask, jsonify, request
from db import get_connection

app = Flask(__name__)

def message_to_dict(row):
    return {
        "id": row["id"],
        "recipient": row["recipient"],
        "text": row["text"],
        "unread": bool(row["unread"]),
        "created_at": row["created_at"]
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/messages")
def create_message():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    recipient = data.get("recipient")
    text = data.get("text")

    if not isinstance(recipient, str) or not recipient.strip():
        return jsonify({"error": "A recipient is required"}), 400

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Message text is required"}), 400

    
    connection = get_connection()

    # RETURNING gives us the values actually stored by the database, including generated fields.
    try:
        row = connection.execute(
            """
            INSERT INTO messages (recipient, text)
            VALUES (?, ?)
            RETURNING id, recipient, text, unread, created_at
            """,
            (recipient, text)
        ).fetchone()

        connection.commit()

        message = {
            "id": row["id"],
            "recipient": row["recipient"],
            "text": row["text"],
            "unread": bool(row["unread"]),
            "created_at": row["created_at"]
        }

        return jsonify(message), 201

    finally:
        connection.close()




@app.get("/messages")
def get_messages():
    recipient = request.args.get("recipient", "").strip()

    if not recipient:
        return jsonify({"error": "A recipient is required"}), 400

    # Pagination uses Python-style indexes: start is inclusive and stop is exclusive.
    raw_start = request.args.get("start")
    raw_stop = request.args.get("stop")

    for name, value in [("start", raw_start), ("stop", raw_stop)]:
        if value is not None:
            if not value.isascii() or not value.isdigit():
                return jsonify({
                    "error": f"{name} must be a non-negative integer"
                }), 400

    start = int(raw_start) if raw_start is not None else 0
    stop = int(raw_stop) if raw_stop is not None else None

    if stop is not None and stop < start:
        return jsonify({
            "error": "stop must be greater than or equal to start"
        }), 400


    connection = get_connection()

    try:
        sql = """
            SELECT id, recipient, text, unread, created_at
            FROM messages
            WHERE recipient = ?
            ORDER BY created_at ASC, id ASC
        """

        parameters = [recipient]

        if stop is not None:
            sql += " LIMIT ? OFFSET ?"
            parameters.extend([stop - start, start])

        elif raw_start is not None:
            sql += " LIMIT -1 OFFSET ?"
            parameters.append(start)

        rows = connection.execute(
            sql, parameters
        ).fetchall()

        result = [
            {
                "id": row["id"],
                "recipient": row["recipient"],
                "text": row["text"],
                "unread": bool(row["unread"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]

        return jsonify(result), 200

    finally:
        connection.close()



@app.post("/messages/unread/fetch")
def fetch_unread_messages():
    recipient = request.args.get("recipient", "").strip()

    if not recipient:
        return jsonify({"error": "A recipient is required"}), 400

    connection = get_connection()

    # Update and return the same messages in one statement so the response reflects their new read state.    
    try:
        rows = connection.execute(
            """
            UPDATE messages
            SET unread = 0
            WHERE recipient = ? AND unread = 1
            RETURNING id, recipient, text, unread, created_at
            """,
            (recipient,)
        ).fetchall()

        connection.commit()

        # RETURNING does not guarantee result order, so sort chronologically before responding.
        rows = sorted(
            rows,
            key=lambda row: (row["created_at"], row["id"])
        )

        result = [
            {
                "id": row["id"],
                "recipient": row["recipient"],
                "text": row["text"],
                "unread": bool(row["unread"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]

        return jsonify(result), 200

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.delete("/messages/<int:message_id>")
def delete_message(message_id):
    connection = get_connection()

    try:
        cursor = connection.execute(
            "DELETE FROM messages WHERE id = ?",
            (message_id,)
        )

        if cursor.rowcount == 0:
            return jsonify({"error": "Message not found"}), 404

        connection.commit()

        return "", 204

    finally:
        connection.close()



@app.delete("/messages")
def delete_multiple_messages():
    data = request.get_json(silent=True)

    # Validate the request
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    ids = data.get("ids")

    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "A non-empty list of IDs is required"}), 400

    if any(type(mid) is not int or mid <= 0 for mid in ids):
        return jsonify({"error": "IDs must be positive integers"}), 400

    if len(ids) != len(set(ids)):
        return jsonify({"error": "Duplicate IDs are not allowed"}), 400

    # Create placeholders for our SQL query
    placeholders = ",".join("?" for _ in ids)

    connection = get_connection()

    try:
        # Batch deletion is all-or-nothing: if any message is missing, roll back the entire deletion.
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.execute(
            f"DELETE FROM messages WHERE id IN ({placeholders})",
            ids
        )

        # Ensure every requested message existed
        if cursor.rowcount != len(ids):
            connection.rollback()
            return jsonify({
                "error": "One or more messages not found"
            }), 404

        connection.commit()

        return jsonify({"deleted_count": cursor.rowcount}), 200

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()




