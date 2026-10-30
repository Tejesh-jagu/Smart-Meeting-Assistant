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

    if not runtime.GROQ_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured.",
        )

    return {"status": "ok", "database": "ok", "groq": "configured", "model": runtime.GROQ_MODEL}
