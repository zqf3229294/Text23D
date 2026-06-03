from app.providers.chat_completions_provider import _chat_messages


def test_chat_messages_use_text_summary_when_provider_does_not_support_images(tmp_path):
    image_path = tmp_path / "part.png"
    image_path.write_bytes(b"image")

    messages = _chat_messages(
        [
            {
                "role": "user",
                "content": "make this bracket",
                "attachments": [
                    {
                        "filename": "part.png",
                        "content_type": "image/png",
                        "storage_path": str(image_path),
                    }
                ],
            }
        ],
        previous_error=None,
        cad_kernel="freecad",
        supports_image_input=False,
    )

    assert isinstance(messages[1]["content"], str)
    assert "Attached reference image(s): part.png" in messages[1]["content"]


def test_chat_messages_emit_image_url_blocks_when_provider_supports_images(tmp_path):
    image_path = tmp_path / "part.png"
    image_path.write_bytes(b"image")

    messages = _chat_messages(
        [
            {
                "role": "user",
                "content": "make this bracket",
                "attachments": [
                    {
                        "filename": "part.png",
                        "content_type": "image/png",
                        "storage_path": str(image_path),
                    }
                ],
            }
        ],
        previous_error=None,
        cad_kernel="freecad",
        supports_image_input=True,
    )

    assert isinstance(messages[1]["content"], list)
    assert messages[1]["content"][1]["type"] == "image_url"
