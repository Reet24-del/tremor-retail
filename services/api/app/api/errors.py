"""A stable error envelope, without echoing uploaded financial records."""

import re

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from ..models.contracts import DataIssue


def data_issue(message: str, file: str | None = None, field: str | None = None, code="invalid_input") -> dict:
    if field is None:
        match = re.search(r"(?:column: |in |Invalid |Blank )(\w+)", message)
        field = match.group(1) if match else None
    rows = re.search(r"rows ([\d, ]+)", message)
    return DataIssue(
        code=code,
        message=message,
        file=file,
        field=field,
        rows=[int(n) for n in re.findall(r"\d+", rows.group(1))] if rows else [],
        action="Correct the indicated field or file and submit again",
    ).model_dump()


async def http_error(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    detail.setdefault("message", "Request could not be completed")
    if "issues" not in detail:
        detail["issues"] = [data_issue(e["error"], e.get("file")) for e in detail.get("errors", [])]
    if not detail["issues"]:
        detail["issues"] = [data_issue(detail["message"], code=f"http_{exc.status_code}")]
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)


async def validation_error(_request: Request, exc: RequestValidationError):
    issues = [
        data_issue(error["msg"], field=".".join(map(str, error["loc"])), code="schema_validation") for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": {"message": "Invalid request fields", "issues": issues}})


async def unexpected_error(_request: Request, _exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "message": "The request failed; inspect run status and retry",
                "issues": [data_issue("Unexpected server error", code="server_error")],
            }
        },
    )
