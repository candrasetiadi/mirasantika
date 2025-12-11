from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import schemas, crud, models

router = APIRouter(prefix="/inventory-movements", tags=["Inventory Movements"])


@router.post("", response_model=schemas.InventoryMovementResponse)
def create_movement(
    payload: schemas.InventoryMovementCreate,
    db: Session = Depends(get_db),
):
    # bisa tambahkan validasi item/location exist
    movement = crud.create_inventory_movement(db, payload)
    return movement


@router.get("", response_model=List[schemas.InventoryMovementResponse])
def list_movements(
    item_id: int | None = None,
    location_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.InventoryMovement)
    if item_id:
        q = q.filter(models.InventoryMovement.item_id == item_id)
    if location_id:
        q = q.filter(models.InventoryMovement.location_id == location_id)
    movements = q.order_by(models.InventoryMovement.created_at.desc()).limit(200).all()
    return movements