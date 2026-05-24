# Text23D Mechanical API

Base URL: `http://localhost:8000`

## Health

`GET /health`

```json
{ "status": "ok" }
```

## Create Conversation

`POST /api/conversations`

Request:

```json
{ "title": "Optional title" }
```

Response:

```json
{
  "id": "conv_...",
  "title": "Optional title",
  "created_at": "2026-05-15T12:00:00+00:00",
  "updated_at": "2026-05-15T12:00:00+00:00",
  "messages": [],
  "generations": []
}
```

## Get Conversation

`GET /api/conversations/{conversation_id}`

Returns the conversation, all messages, and all generations.

## Submit Message

`POST /api/conversations/{conversation_id}/messages`

Request:

```json
{ "content": "make a 40 mm cube with a 10 mm through-hole" }
```

Response:

```json
{
  "message": {
    "id": "msg_...",
    "conversation_id": "conv_...",
    "role": "user",
    "content": "make a 40 mm cube with a 10 mm through-hole",
    "generation_id": null,
    "created_at": "2026-05-15T12:00:00+00:00"
  },
  "generation": {
    "id": "gen_...",
    "conversation_id": "conv_...",
    "status": "queued",
    "prompt": "make a 40 mm cube with a 10 mm through-hole",
    "assistant_summary": null,
    "error": null,
    "attempt_count": 0,
    "artifacts": {
      "step": false,
      "glb": false,
      "script": false,
      "log": false
    },
    "created_at": "2026-05-15T12:00:00+00:00",
    "updated_at": "2026-05-15T12:00:00+00:00"
  }
}
```

## Get Generation

`GET /api/generations/{generation_id}`

Status values:

- `queued`
- `running`
- `succeeded`
- `failed`

## Download Artifact

`GET /api/generations/{generation_id}/artifacts/{kind}`

Kinds:

- `step`
- `glb`
- `script`
- `log`
