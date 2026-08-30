from types import SimpleNamespace

import pytest

from beacon_call.scene import SceneAnalysisError, analyze_scene


class FakeResponses:
    def __init__(self, output_text: str):
        self.output_text = output_text
        self.request: dict[str, object] | None = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str):
        self.responses = FakeResponses(output_text)


def test_scene_analysis_uses_image_input_and_structured_output() -> None:
    client = FakeClient(
        '{"people_count":2,"scene_description":"Two people stand beside a doorway."}'
    )
    analysis, model = analyze_scene(b"jpeg-data", client=client, model="vision-test")

    assert model == "vision-test"
    assert analysis.people_count == 2
    assert client.responses.request is not None
    assert client.responses.request["store"] is False
    image = client.responses.request["input"][0]["content"][1]
    assert image["type"] == "input_image"
    assert image["image_url"].startswith("data:image/jpeg;base64,")
    assert client.responses.request["text"]["format"]["type"] == "json_schema"


def test_scene_analysis_rejects_invalid_model_output() -> None:
    with pytest.raises(SceneAnalysisError):
        analyze_scene(b"jpeg-data", client=FakeClient("not-json"), model="vision-test")
