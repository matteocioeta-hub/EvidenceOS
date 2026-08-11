from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("EVIDENCEOS_ENV", "development")
    log_level: str = os.getenv("EVIDENCEOS_LOG_LEVEL", "INFO")
    max_input_chars: int = int(os.getenv("EVIDENCEOS_MAX_INPUT_CHARS", "1000000"))

settings = Settings()
