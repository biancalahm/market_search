import os

# Lightweight .env loader (avoid dependency if python-dotenv is not installed)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # Do not override existing environment variables
            os.environ.setdefault(k, v)

try:
    # Prefer pydantic-settings when available
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field

    class Settings(BaseSettings):
        TELEGRAM_BOT_TOKEN: str | None = Field(None, alias="TELEGRAM_BOT_TOKEN")
        GEMINI_API_KEY: str | None = Field(None, alias="GEMINI_API_KEY")
        DATABASE_URL: str = Field(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./market.db"), alias="DATABASE_URL")
        PORT: int = Field(8000, alias="PORT")
        PROVEDOR_IA: str = Field(os.getenv("PROVEDOR_IA"), alias="PROVEDOR_IA")
        OLLAMA_MODEL: str = Field(os.getenv("OLLAMA_MODEL"), alias="OLLAMA_MODEL")


        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    settings = Settings()
except Exception:
    # Minimal fallback when pydantic-settings (or pydantic BaseSettings) is not installed
    class Settings:
        TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
        GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
        DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./market.db")
        PORT: int = int(os.getenv("PORT", "8000"))

    settings = Settings()