from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class HealRequest(BaseModel):
    # Placeholder fields – adjust to your actual healing payload later
    target_id: str
    issue_type: str | None = None
    metadata: dict | None = None


class ConfirmRequest(BaseModel):
    # Placeholder fields – adjust to your actual confirmation payload later
    target_id: str
    success: bool
    details: str | None = None


app = FastAPI(title="Self Heal Engine", version="0.1.0")


@app.get("/health")
async def health_check() -> dict:
    """
    Simple health check endpoint.
    """
    return {"status": "ok"}


@app.post("/heal")
async def heal(request: HealRequest) -> dict:
    """
    Placeholder heal endpoint.
    Currently not implemented – returns HTTP 501.
    """
    raise HTTPException(status_code=501, detail="Heal endpoint not implemented yet")


@app.post("/confirm")
async def confirm(request: ConfirmRequest) -> dict:
    """
    Placeholder confirm endpoint.
    Currently not implemented – returns HTTP 501.
    """
    raise HTTPException(status_code=501, detail="Confirm endpoint not implemented yet")
