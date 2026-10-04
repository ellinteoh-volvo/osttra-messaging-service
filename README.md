# Messaging Service

A lightweight REST API for submitting, retrieving, and deleting plain-text messages.

The service is implemented in Python using Flask and SQLite. SQLite was chosen to keep the solution self-contained and easy to run locally without requiring external infrastructure.

## Requirements Coverage

| Requirement | Implementation |
|---|---|
| Submit a plain-text message to a recipient | `POST /messages` |
| Fetch unread messages | `POST /messages/unread/fetch` |
| Delete a single message | `DELETE /messages/<id>` |
| Delete multiple messages | `DELETE /messages` |
| Retrieve messages including previously fetched messages | `GET /messages` |
| Order messages by time | Messages are returned oldest first |
| Support start/stop indexes | `GET /messages?recipient=alice&start=1&stop=3` |
| REST API only | Implemented with Flask |
| No authentication/authorization required | Intentionally omitted |

## Runtime Requirements

- Python 3.9 or newer
- SQLite 3.35.0 or newer, because the API uses SQLite `RETURNING`
- Tested with Python 3.13

## Assumptions

- A recipient is identified by a non-empty string.
- Message content is plain text only.
- Fetching unread messages also marks those messages as read.
- Batch deletion is all-or-nothing: if any requested message does not exist, no messages are deleted.
- Message ordering is oldest first, using creation time and message ID for deterministic ordering.
- Pagination uses Python-style indexes: `start` is inclusive and `stop` is exclusive.
- Authentication and authorization are intentionally omitted because they are outside the assignment scope.

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize the database

```bash
python db.py
```

## Run the Service

Start the Flask API with:

```bash
flask --app app run
```

The service will be available at:

```text
http://127.0.0.1:5000
```

## API Usage

### Create a message

```bash
curl -X POST http://127.0.0.1:5000/messages \
  -H "Content-Type: application/json" \
  -d '{"recipient":"alice","text":"Hello Alice"}'
```

Example response:

```json
{
  "created_at": "2026-10-03 17:30:00",
  "id": 1,
  "recipient": "alice",
  "text": "Hello Alice",
  "unread": true
}
```

### Fetch unread messages

Fetching unread messages also marks them as read.

```bash
curl -X POST "http://127.0.0.1:5000/messages/unread/fetch?recipient=alice"
```

Example response:

```json
[
  {
    "created_at": "2026-10-03 17:30:00",
    "id": 1,
    "recipient": "alice",
    "text": "Hello Alice",
    "unread": false
  }
]
```

Calling the same endpoint again returns an empty list if there are no unread messages:

```json
[]
```

### Retrieve messages

Retrieve all messages for a recipient, including messages that have already been fetched:

```bash
curl "http://127.0.0.1:5000/messages?recipient=alice"
```

Messages are returned oldest first.

Pagination can be applied using `start` and/or `stop`. `start` is inclusive and `stop` is exclusive.

For example, to return messages at positions 1 and 2:

```bash
curl "http://127.0.0.1:5000/messages?recipient=alice&start=1&stop=3"
```

You can also provide only `start`:

```bash
curl "http://127.0.0.1:5000/messages?recipient=alice&start=2"
```

or only `stop`:

```bash
curl "http://127.0.0.1:5000/messages?recipient=alice&stop=3"
```

### Delete a single message

Delete a message by its ID:

```bash
curl -X DELETE http://127.0.0.1:5000/messages/1
```

A successful deletion returns:

```text
HTTP 204 No Content
```

If the message does not exist, the API returns:

```json
{
  "error": "Message not found"
}
```

### Delete multiple messages

Delete multiple messages by providing their IDs:

```bash
curl -X DELETE http://127.0.0.1:5000/messages \
  -H "Content-Type: application/json" \
  -d '{"ids":[1,2,3]}'
```

A successful batch deletion returns:

```json
{
  "deleted_count": 3
}
```

with HTTP status:

```text
HTTP 200 OK
```

Batch deletion is all-or-nothing. If any requested message does not exist, no messages are deleted and the API returns:

```json
{
  "error": "One or more messages not found"
}
```

### Health check

Check that the API process is running:

```bash
curl http://127.0.0.1:5000/health
```

Example response:

```json
{
  "status": "ok"
}
```

## Testing

Run the automated test suite with:

```bash
python -m pytest -v
```

The tests cover:

- Message creation and retrieval
- Recipient isolation and normalization
- Unread-message fetching and read-state updates
- Single-message deletion
- Atomic batch deletion and rollback behavior
- Pagination using `start` and `stop`
- Pagination boundary and range validation
- Input validation and error handling
- Batch-delete input validation
- Health endpoint behavior

Each test uses its own temporary SQLite database, so tests do not affect the local application database or each other.

## Test Coverage

The automated tests cover the main API behavior, including message creation and retrieval, unread-state transitions, recipient isolation, deletion, atomic batch deletion, pagination, validation, and error handling.

Coverage can be measured with:

```bash
python -m pytest --cov=app --cov=db --cov-report=term-missing
```

## Production Considerations

This implementation is intentionally lightweight and optimized for local execution rather than production deployment.

For a production environment, I would consider:

- Replacing SQLite with a production database such as PostgreSQL to support higher concurrency, replication, backups, and failover.
- After replacing the local SQLite database with a shared production database, run multiple stateless API instances behind a load balancer for redundancy and horizontal scaling.
- Adding idempotency support to `POST /messages` to prevent duplicate messages when clients retry after timeouts or network failures.
- Using managed database backups and tested recovery procedures based on defined RTO and RPO requirements.
- Extending health checks with readiness checks for critical dependencies such as the database.
- Using cursor-based pagination for very large datasets, while keeping index-based pagination here because the assignment explicitly requires `start` and `stop` indexes.
- Adding authentication, authorization, observability, and rate limiting if the service were exposed in a real production environment.
- The batch-delete endpoint sends message IDs in the body of a `DELETE` request. This works with the documented `curl` usage, although some HTTP clients and intermediaries may handle DELETE request bodies inconsistently. For broader compatibility, an alternative design could use a `POST /messages/batch-delete` action endpoint.
- In production, add centralized structured logging, service metrics, and alerting. Key signals would include request rate, response latency, HTTP 4xx/5xx rates, database errors, and health/readiness failures. Request IDs should be used for correlation, and message contents should not be logged.
- Synthetic API monitoring could be added using tools such as Postman Monitors to periodically verify key endpoints and response times, alongside application logs and service metrics for deeper diagnosis.
- Authentication and authorization are intentionally omitted because they are outside the assignment scope. In production, access should be authenticated and authorized per recipient or user.
- Production deployment should use HTTPS, rate limiting, request-size limits, secure configuration management, and least-privilege database access.
- Message contents should not be written to application logs or other monitoring systems.
- For production, I’d define SLIs around availability, latency, correctness, and durability. For example, we could measure the percentage of valid requests succeeding and p95 latency for the critical message flows, then agree SLO targets with stakeholders based on business criticality.