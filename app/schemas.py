from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class LocationBase(BaseModel):
    id: int
    name: str
    code: str

    class Config:
        orm_mode = True


class SessionCreate(BaseModel):
    location_id: int
    type: str  # "FULL" | "PARTIAL"
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    notes: Optional[str] = None


class SessionResponse(BaseModel):
    id: int
    code: str
    location: LocationBase
    status: str
    type: str
    total_items: int
    items_scanned: int
    progress_percent: Decimal
    snapshot_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ScanBatch(BaseModel):
    zone: Optional[str] = None
    scanned_at: Optional[datetime] = None
    tags: List[str]


class InventoryMovementCreate(BaseModel):
    item_id: int
    location_id: int
    qty_change: Decimal
    reason: str  # "SALE","RESTOCK",...
    reference_id: Optional[str] = None


class InventoryMovementResponse(BaseModel):
    id: int
    item_id: int
    location_id: int
    qty_change: Decimal
    reason: str
    reference_id: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True