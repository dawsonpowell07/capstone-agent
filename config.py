from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === OpenAI / Gemini / LangSmith ===
    openai_api_key: str
    gemeni_api_key: str
    langsmith_api_key: str

    # === Amadeus API ===
    amadeus_api_secret: str
    amadeus_api_key: str
    amadeus_token_url: str
    amadeus_base_url: str

    # === Auth0 ===
    auth0_api_audience: str
    auth0_domain: str
    auth0_issuer: str
    auth0_algorithms: str
    auth0_client_id: str

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
