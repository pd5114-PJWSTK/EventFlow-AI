from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.planner import ConstraintCheckRequest, ConstraintCheckResponse
from app.services.validation_service import ValidationError, validate_event_constraints


router = APIRouter(prefix="/api/planner", tags=["planner"])


@router.post("/validate-constraints", response_model=ConstraintCheckResponse)
def validate_constraints_endpoint(
    payload: ConstraintCheckRequest,
    db: Session = Depends(get_db),
) -> ConstraintCheckResponse:
    try:
        return validate_event_constraints(db, payload.event_id)
    except ValidationError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
