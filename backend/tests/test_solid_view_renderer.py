from app.solid_view_renderer import render_solid_view_preview


def test_solid_view_renderer_writes_projection_png(tmp_path):
    output_path = tmp_path / "solid-view.png"
    result = render_solid_view_preview(
        {
            "source": "freecad-brep",
            "truncated": False,
            "objects": [
                {
                    "bounds": {
                        "x_min": 0.0,
                        "x_max": 40.0,
                        "y_min": 0.0,
                        "y_max": 30.0,
                        "z_min": 0.0,
                        "z_max": 20.0,
                    },
                    "edges": [
                        [[0.0, 0.0, 0.0], [40.0, 0.0, 0.0]],
                        [[40.0, 0.0, 0.0], [40.0, 30.0, 0.0]],
                        [[40.0, 30.0, 0.0], [0.0, 30.0, 0.0]],
                        [[0.0, 30.0, 0.0], [0.0, 0.0, 0.0]],
                    ],
                }
            ],
        },
        output_path,
        window_size=(640, 480),
    )

    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result["renderer"] == "solid-projection"
    assert result["edge_count"] == 4
