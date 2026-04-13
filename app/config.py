from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    kma_api_key: str = ""
    airkorea_api_key: str = ""
    gemini_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "weather_kb"
    llm_provider: str = "gemini"
    rain_prob_threshold: int = 60
    rain_mm_threshold: float = 1.0
    pm25_threshold: int = 35
    pm10_threshold: int = 80
    regions: dict = {
        "마곡":      {"nx": 58, "ny": 126, "sido": "서울", "station": "강서구"},
        "선릉":      {"nx": 61, "ny": 125, "sido": "서울", "station": "강남구"},
        "미아사거리": {"nx": 61, "ny": 127, "sido": "서울", "station": "강북구"},
    }

settings = Settings()
