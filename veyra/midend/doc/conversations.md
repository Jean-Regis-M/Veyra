# Conversations and history

Use `POST /conversations`, `GET /conversations`,
`GET /conversations/{id}`, `POST /conversations/{id}/messages`, and
`DELETE /conversations/{id}`. Conversation history is separate from execution
history. Each conversation records provider/model metadata and linked
execution IDs. Messages are structured role/content records.

The current implementation is process-local. A production multi-worker
deployment should move this store to an authenticated shared persistence layer
with an explicit retention policy.
