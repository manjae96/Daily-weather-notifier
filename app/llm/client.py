"""LLM 클라이언트 추상화. 현재는 Gemini, 추후 Ollama 추가 가능."""
from abc import ABC, abstractmethod
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings

class LLMClient(ABC):
    @abstractmethod
    async def generate(self, system: str, user: str) -> str: ...
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

_retry_on_server_error = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)

class GeminiClient(LLMClient):
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.gen_model = "gemini-2.5-flash"
        self.embed_model = "text-embedding-004"

    @_retry_on_server_error
    async def generate(self, system: str, user: str) -> str:
        resp = self.client.models.generate_content(
            model=self.gen_model,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.4),
            contents=user,
        )
        return resp.text or ""

    @_retry_on_server_error
    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.models.embed_content(model=self.embed_model, contents=texts)
        return [e.values for e in resp.embeddings]

def get_client() -> LLMClient:
    if settings.llm_provider == "gemini":
        return GeminiClient()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
