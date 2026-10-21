from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import runtime
from .api import auth, health, meetings, reports

app = FastAPI(title="Smart Meeting Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=runtime.FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(meetings.router)
app.include_router(reports.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, error):
    # Pydantic's default response includes submitted values, which can contain passwords.
    details = [
        {"loc": item.get("loc"), "msg": item.get("msg"), "type": item.get("type")}
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


runtime.create_table()
