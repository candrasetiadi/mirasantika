from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from .. import schemas, crud

router = APIRouter(prefix="/stock-opname-sessions", tags=["Stock Opname"])


def get_current_user_id() -> int:
    # untuk hackathon, hardcode user
    return 1


@router.post("", response_model=schemas.SessionResponse)
def create_session(
    payload: schemas.SessionCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        session = crud.create_opname_session(db, payload, user_id=user_id)
        db.refresh(session)
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[schemas.SessionResponse])
def list_sessions(
    location_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    sessions = crud.list_sessions(db, location_id=location_id)
    return sessions


@router.get("/{session_id}", response_model=schemas.SessionResponse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/start", response_model=schemas.SessionResponse)
def start_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = crud.start_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/scans", response_model=schemas.SessionResponse)
def submit_scan_batch(
    session_id: int,
    batch: schemas.ScanBatch,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        session = crud.process_scan_batch(db, session_id, batch, user_id=user_id)
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))