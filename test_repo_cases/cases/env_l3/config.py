# EnvironmentError Level 3 — Multiple missing env vars in config class
import os


class AppConfig:
    def __init__(self) -> None:
        self.db_url = os.environ.get("DATABASE_URL")
        self.secret = os.environ.get("SECRET_KEY")
        self.api_url = os.environ.get("EXTERNAL_API_URL")

    def validate(self) -> None:
        required = ["DATABASE_URL", "SECRET_KEY", "EXTERNAL_API_URL"]
        for key in required:
            if not os.environ.get(key):
                raise EnvironmentError(f"environment variable {key} not set")
