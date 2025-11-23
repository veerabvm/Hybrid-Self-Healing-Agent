"""
Self-Healing Engine API

A FastAPI-based service for generating robust web element locators
that can adapt to DOM changes and UI modifications.
"""

import uuid
import re
from typing import Dict, List, Any, Optional, Literal
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .parser import parse_html
from .heuristics import generate_candidates as generate_heuristic_candidates
from .hierarchy_search import find_moved_candidates
from .ranker import score_candidates, extract_features
from .llm_adapter import LLMAdapter
from .verify import build_verify_action, is_destructive
from .storage import save_snapshot, append_training_record


app = FastAPI(
    title="Self-Healing Engine",
    description="AI-powered web element locator healing service",
    version="1.0.0",
)


class HealRequest(BaseModel):
    request_id: str
    test_id: Optional[str] = None
    page_url: Optional[str] = None

    original_locator: str
    original_locator_type: Literal[
        "id","css","xpath","name","link_text","partial_link_text","class_name","text"
    ]

    action: Literal["click","send_keys","get_text","submit","none"] | str

    page_html: str
    element_outer_html: Optional[str] = None

    anchors: Optional[List[str]] = None
    prev_sibling_text: Optional[str] = None
    next_sibling_text: Optional[str] = None

    screenshot_base64: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    pii_masked: Optional[bool] = True


class HealResponse(BaseModel):
    """Response model for healing operation."""
    request_id: str
    healed_locator: Optional[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    auto_apply_index: int
    verify_action: Optional[Dict[str, Any]]
    warning: Optional[str]
    message: str


class ConfirmRequest(BaseModel):
    """Request model for confirming a healing result."""
    request_id: str
    accepted_index: int
    metadata: Optional[Dict[str, Any]] = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/heal", response_model=HealResponse)
async def heal_locator(request: HealRequest, background_tasks: BackgroundTasks):
    """
    Main healing endpoint that orchestrates the full locator recovery process.

    Steps:
    1. Parse HTML
    2. Run heuristics
    3. Run hierarchy/moved-element search
    4. Aggregate all candidates
    5. Extract features & rank candidates
    6. If needed, call LLM adapter for additional candidates
    7. Validate LLM candidates
    8. Sort and return top candidates + verify_action
    """
    try:
        # Check for PII if not masked
        pii_detected = False
        if request.pii_masked is False:
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
            if re.search(email_pattern, request.page_html) or re.search(phone_pattern, request.page_html):
                pii_detected = True

        # Parse HTML
        html_valid = True
        try:
            soup = parse_html(request.page_html)
        except Exception:
            soup = None
            html_valid = False

        # Placeholder logic
        if html_valid:
            healed_locator = {
                "locator": request.original_locator,
                "type": request.original_locator_type,
                "score": 1.0
            }
        else:
            healed_locator = None

        candidates = []
        auto_apply_index = -1
        verify_action = None
        warning = "PII detected" if pii_detected else None
        message = "updated API: received payload"

        # Save snapshot in background (placeholder, adjust as needed)
        background_tasks.add_task(
            save_snapshot,
            request.request_id,
            request.page_html,
            candidates,
            auto_apply_index,
            {
                "original_locator": request.original_locator,
                "locator_type": request.original_locator_type,
                "healed_locator": healed_locator
            }
        )

        return HealResponse(
            request_id=request.request_id,
            healed_locator=healed_locator,
            candidates=candidates,
            auto_apply_index=auto_apply_index,
            verify_action=verify_action,
            warning=warning,
            message=message
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Healing failed: {str(e)}")


@app.post("/confirm")
async def confirm_healing(request: ConfirmRequest):
    """Confirm a healing result and store training data."""
    try:
        # Load the snapshot
        # In a real implementation, you'd load from storage
        # For now, just append a training record

        training_record = {
            "request_id": request.request_id,
            "accepted_index": request.accepted_index,
            "metadata": request.metadata or {}
        }

        append_training_record(training_record)

        return {"status": "confirmed", "request_id": request.request_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Initialize the application."""
    # Load models, setup connections, etc.
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    pass
