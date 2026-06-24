"""Dependências compartilhadas da camada de API."""

from fastapi import Request

from services.pipeline_protocol import PipelineProtocol


def get_pipeline(request: Request) -> PipelineProtocol:
    """Devolve a pipeline criada no `lifespan` e guardada em `app.state`.

    Em testes, sobrescreva via `app.dependency_overrides[get_pipeline]`.
    """
    return request.app.state.pipeline
