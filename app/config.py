from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_embedding_model: str = ""
    database_path: str = "data/knowledge.db"
    upload_dir: str = "data/uploads"
    similarity_threshold: float = 0.72
    top_k: int = 8
    chunk_size: int = 3000
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
settings = Settings()