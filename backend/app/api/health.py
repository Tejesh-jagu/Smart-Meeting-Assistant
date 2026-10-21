from fastapi import APIRouter, HTTPException

from .. import runtime

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    try:
        with runtime.psycopg.connect(**runtime.DB_CONFIG) as connection:
            connection.execute("SELECT 1")
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL is unavailable.",
        ) from error

    try:
        with runtime.urlopen(f"{runtime.OLLAMA_BASE_URL}/api/tags", timeout=5) as response:
            installed_models = runtime.json.loads(response.read().decode("utf-8")).get("models", [])
    except (runtime.URLError, OSError, runtime.json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Ollama is unavailable.",
        ) from error

    if not any(model.get("name") == runtime.OLLAMA_MODEL for model in installed_models):
        raise HTTPException(
            status_code=503,
            detail=f"Configured Ollama model {runtime.OLLAMA_MODEL} is not installed.",
        )

    return {"status": "ok", "database": "ok", "ollama": "ok", "model": runtime.OLLAMA_MODEL}
