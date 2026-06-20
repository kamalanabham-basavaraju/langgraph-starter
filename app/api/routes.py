from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.graph.workflow import graph
from app.models.incident import IncidentRequest, IncidentResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["incidents"])


@router.post("/incidents/resolve", response_model=IncidentResponse)
def resolve_incident(payload: IncidentRequest) -> IncidentResponse:
    try:
        state = graph.invoke({"incident": payload.incident})
        return IncidentResponse.model_validate(state)
    except (ValueError, RuntimeError) as exc:
        logger.exception("Incident resolution failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected incident resolution failure")
        raise HTTPException(status_code=500, detail="Incident resolution failed") from exc
