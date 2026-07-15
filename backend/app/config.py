from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    movie_dir: str = "/media/movies"
    series_dir: str = "/media/series"
    interactive_dir: str = "/media/interactive"
    log_dir: str = "/logs"
    port: int = 9095
    tz: str = "America/Denver"
    default_preset: str = "Fast 720p30"
    redis_url: str = "redis://redis:6379/0"

    batch_start_hour: int = 1
    batch_start_minute: int = 30
    batch_stop_hour: int = 5
    batch_stop_minute: int = 30
    movie_min_size_bytes: int = int(1.5 * 1024 * 1024 * 1024)
    movie_batch_count: int = 5

    video_extensions: tuple[str, ...] = (
        ".mp4", ".mkv", ".avi", ".mov", ".m4v", ".wmv", ".mpg", ".mpeg", ".ts",
    )

    class Config:
        env_file = ".env"


settings = Settings()
