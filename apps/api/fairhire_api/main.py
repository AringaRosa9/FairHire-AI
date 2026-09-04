import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .evidence_routes import router as evidence_router
from .governance_routes import router as governance_router
from .routes import router
from .schemas import ProblemDetails
from .telemetry import observe_request

settings = get_settings()
app = FastAPI(
    title="FairHire AI API",
    version=settings.app_version,
    description=(
        "Organization-scoped recruitment AI assurance API. "
        "Responses are risk evidence, not legal determinations."
    ),
    openapi_url="/v1/openapi.json",
    docs_url="/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Organization-ID",
        "X-Dev-User",
        "X-Scanner-Attestation",
    ],
)


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        observe_request(request, 500, time.perf_counter() - started)
        raise
    observe_request(request, response.status_code, time.perf_counter() - started)
    return response


@app.exception_handler(HTTPException)
async def http_problem(request: Request, exc: HTTPException) -> JSONResponse:
    problem = ProblemDetails(
        title="Request rejected",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=str(request.url.path),
    )
    return JSONResponse(
        problem.model_dump(exclude_none=True),
        status_code=exc.status_code,
        media_type="application/problem+json",
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
    problem = ProblemDetails(
        title="Validation failed",
        status=422,
        detail="The request does not match the published contract.",
        instance=str(request.url.path),
        code="validation_error",
    )
    return JSONResponse(
        {**problem.model_dump(exclude_none=True), "errors": exc.errors()},
        status_code=422,
        media_type="application/problem+json",
    )


app.include_router(router)
app.include_router(governance_router)
app.include_router(evidence_router)
