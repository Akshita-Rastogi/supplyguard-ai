import httpx
import pytest

from supplyguard.domain.models import Intent
from supplyguard.infrastructure.ollama import OllamaClient, OllamaUnavailable


@pytest.mark.asyncio
async def test_empty_generation_is_rejected():
    async def handler(request):
        return httpx.Response(200, json={"response": ""})

    client = OllamaClient("http://local", "chat", "embed")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaUnavailable):
        await client.generate("question", "[S1] evidence")
    await client.close()


@pytest.mark.asyncio
async def test_embedding_count_is_validated():
    async def handler(request):
        return httpx.Response(200, json={"embeddings": []})

    client = OllamaClient("http://local", "chat", "embed")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaUnavailable):
        await client.embeddings(["one"])
    await client.close()


@pytest.mark.asyncio
async def test_intent_classifier_accepts_only_typed_json_intent():
    async def handler(request):
        return httpx.Response(200, json={"response": '{"intent":"analytics"}'})

    client = OllamaClient("http://local", "chat", "embed")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await client.classify_intent("Rank FEMA states") == Intent.ANALYTICS
    await client.close()


@pytest.mark.asyncio
async def test_intent_classifier_rejects_unstructured_output():
    async def handler(request):
        return httpx.Response(200, json={"response": "analytics"})

    client = OllamaClient("http://local", "chat", "embed")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaUnavailable):
        await client.classify_intent("Rank FEMA states")
    await client.close()
