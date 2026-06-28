# Text23D Mechanical API

Base URL: `http://localhost:8000`

## Health

`GET /health`

```json
{ "status": "ok" }
```

## App Config

`GET /api/config`

Returns feature flags that the frontend should honor.

```json
{
  "features": {
    "image_input_enabled": false,
    "image_max_upload_bytes": 5242880,
    "image_max_count_per_message": 4,
    "image_allowed_content_types": ["image/png", "image/jpeg", "image/webp"]
  }
}
```

## Upload Image Attachment

`POST /api/conversations/{conversation_id}/attachments/images?filename=reference.png`

Body: raw image bytes. Set `Content-Type` to an allowed image media type.

Response:

```json
{
  "id": "img_...",
  "conversation_id": "conv_...",
  "message_id": null,
  "filename": "reference.png",
  "content_type": "image/png",
  "size_bytes": 12345,
  "created_at": "2026-05-15T12:00:00+00:00"
}
```

## Download Image Attachment

`GET /api/conversations/{conversation_id}/attachments/images/{attachment_id}`

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
{
  "content": "make a 40 mm cube with a 10 mm through-hole",
  "attachment_ids": []
}
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
      "stl": false,
      "native": false,
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

## Get Generation Events

`GET /api/generations/{generation_id}/events`

Returns stored progress events for script and agent-mode generations.

```json
[
  {
    "id": "evt_...",
    "generation_id": "gen_...",
    "event_type": "tool_call",
    "message": "Calling FreeCAD tool: execute_code",
    "tool_name": "execute_code",
    "data": {},
    "has_asset": false,
    "created_at": "2026-05-15T12:00:01+00:00"
  }
]
```

Event types:

- `status`
- `tool_call`
- `tool_result`
- `screenshot`
- `error`
- `artifact`

## Stream Generation Events

`WS /api/generations/{generation_id}/stream`

Streams existing and new generation events, then sends a final `done` payload when the generation reaches `succeeded` or `failed`.

## Download Event Asset

`GET /api/generations/{generation_id}/events/{event_id}/asset`

Returns an event asset such as an agent-mode view image when `has_asset` is true.

## Download Artifact

`GET /api/generations/{generation_id}/artifacts/{kind}`

Kinds:

- `step`
- `glb`
- `stl`
- `native`
- `script`
- `log`
