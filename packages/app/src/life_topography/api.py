"""Local HTTP adapter."""

from fastapi import FastAPI

app = FastAPI(
    title="Life Topography",
    description="Local-first personal evidence vault",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return process health without leaking configuration or vault state."""

    return {
        "service": "life-topography",
        "status": "ok",
        "stage": "pre-alpha",
    }
