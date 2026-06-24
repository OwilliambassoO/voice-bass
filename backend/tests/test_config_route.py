"""Teste da rota /config com pipeline falsa (sem ML).

Pré-condição (Regra 5): importar `api.config_routes` não pode disparar import
de whisper/torch — caso contrário este teste não roda sem o stack de ML.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.config_routes import router
from api.dependencies import get_pipeline
from domain.voice import VoiceModel


class FakePipeline:
    def get_available_voices(self) -> list[VoiceModel]:
        return [VoiceModel(name="fake", pth_path="/x/fake.pth", index_path=None)]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    return TestClient(app)


def test_config_returns_expected_shape():
    res = _client().get("/config")
    assert res.status_code == 200

    data = res.json()
    assert {"voices", "hang_options", "rvc_models"} <= data.keys()
    assert data["rvc_models"] == [{"id": "fake", "label": "fake"}]
    # vozes TTS e opções de pausa (hangover) fixas preservadas
    assert any(v["id"] == "pt-BR-AntonioNeural" for v in data["voices"])
    assert {opt["ms"] for opt in data["hang_options"]} == {300, 400, 500}
