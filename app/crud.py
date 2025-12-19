from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from . import models, schemas


# ==============================
# Generate Session Code
# ==============================
def generate_session_code(db: Session, location_code: str) -> str:
    today = datetime.today().strftime("%Y%m%d")
    prefix = f"SO-{location_code}-{today}"

    count = (
        db.query(models.StockOpnameSession)
        .filter(models.StockOpnameSession.code.like(f"{prefix}%"))
        .count()
    )

    return f"{prefix}-{count + 1:03d}"


# ==============================
# Create New Stock Opname Session
# ==============================
def create_opname_session(db: Session, payload: schemas.SessionCreate, user_id: int | None = None):
    location = db.query(models.Location).filter(models.Location.id == payload.location_id).first()
    if not location:
        raise ValueError("Location not found")

    now = datetime.utcnow()
    code = generate_session_code(db, location.code)

    # Count items related to this location
    total_items = (
        db.query(func.count(models.ItemLocation.id))
        .filter(models.ItemLocation.location_id == payload.location_id)
        .scalar()
    ) or 0

    # Create session
    session = models.StockOpnameSession(
        code=code,
        location_id=payload.location_id,
        snapshot_at=now,
        type=payload.type,
        status="PLANNED",
        scheduled_start_at=payload.scheduled_start_at,
        scheduled_end_at=payload.scheduled_end_at,
        notes=payload.notes,
        total_items=total_items,
        items_scanned=0,
        created_by=user_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Snapshot: Save system qty into stock_opname_items
    item_locations = (
        db.query(models.ItemLocation)
        .filter(models.ItemLocation.location_id == payload.location_id)
        .all()
    )

    for il in item_locations:
        system_qty = float(il.system_qty or 0)

        db.add(
            models.StockOpnameItem(
                session_id=session.id,
                item_id=il.item_id,
                system_qty=system_qty,
                movement_qty=0,
                effective_qty=system_qty,
                counted_qty=0,
                variance_qty=0,
                variance_value=0,
                status="OK",
            )
        )

    db.commit()
    return session


# ==============================
# Start Session
# ==============================
def start_session(db: Session, session_id: int):
    session = db.query(models.StockOpnameSession).get(session_id)
    if not session:
        return None

    session.status = "IN_PROGRESS"
    session.started_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


# ==============================
# Get Session
# ==============================
def get_session(db: Session, session_id: int):
    return (
        db.query(models.StockOpnameSession)
        .filter(models.StockOpnameSession.id == session_id)
        .first()
    )


# ==============================
# List Sessions
# ==============================
def list_sessions(db: Session, location_id: int | None = None):
    q = db.query(models.StockOpnameSession).join(models.Location)

    if location_id:
        q = q.filter(models.StockOpnameSession.location_id == location_id)

    return q.order_by(models.StockOpnameSession.created_at.desc()).all()


# ==============================
# Compute Movement Qty
# ==============================
def compute_movement_qty_for_item(db: Session, session: models.StockOpnameSession, item_id: int):
    """
    Hitung total pergerakan stok sejak snapshot hingga sekarang.
    """
    if not session.snapshot_at:
        return 0.0

    total_change = (
        db.query(func.coalesce(func.sum(models.InventoryMovement.qty_change), 0))
        .filter(models.InventoryMovement.item_id == item_id)
        .filter(models.InventoryMovement.location_id == session.location_id)
        .filter(models.InventoryMovement.created_at > session.snapshot_at)
        .scalar()
    )

    return float(total_change or 0)


# ==============================
# Process RFID Scan Batch
# ==============================
def process_scan_batch(
    db: Session,
    session_id: int,
    batch: schemas.ScanBatch,
    user_id: int | None = None,
):
    session = get_session(db, session_id)

    if not session:
        raise ValueError("Session not found")

    if session.status != "IN_PROGRESS":
        raise ValueError("Session is not IN_PROGRESS")

    scanned_at = batch.scanned_at or datetime.utcnow()
    tags = batch.tags

    # ================================
    # ANTI DUPLICATE RFID TAG LOGIC
    # ================================
    existing_tags = set(
        t[0]
        for t in db.query(models.StockOpnameScan.tag_uid)
        .filter(
            models.StockOpnameScan.session_id == session_id,
            models.StockOpnameScan.tag_uid.in_(tags),
        )
        .all()
    )

    new_tags = [tag for tag in tags if tag not in existing_tags]

    # If all tags are duplicates, exit early
    if not new_tags:
        session.updated_at = datetime.utcnow()
        db.commit()
        return session

    # ================================
    # Resolve RFID tag to item_id
    # ================================
    rfid_rows = (
        db.query(models.RFIDTag)
        .filter(models.RFIDTag.tag_uid.in_(new_tags))
        .all()
    )

    # Count items based only on new tags
    counts: dict[int, int] = {}
    tag_to_item: dict[str, int] = {}

    for row in rfid_rows:
        counts[row.item_id] = counts.get(row.item_id, 0) + 1
        tag_to_item[row.tag_uid] = row.item_id

    # ================================
    # Insert raw scans
    # ================================
    for tag in new_tags:
        db.add(
            models.StockOpnameScan(
                session_id=session_id,
                tag_uid=tag,
                item_id=tag_to_item.get(tag),
                zone=batch.zone,
                scanned_at=scanned_at,
                scanned_by=user_id,
            )
        )

    # ================================
    # Update stock_opname_items
    # ================================
    for item_id, count in counts.items():
        oi = (
            db.query(models.StockOpnameItem)
            .filter(
                models.StockOpnameItem.session_id == session_id,
                models.StockOpnameItem.item_id == item_id,
            )
            .first()
        )

        if not oi:
            oi = models.StockOpnameItem(
                session_id=session_id,
                item_id=item_id,
                system_qty=0,
                movement_qty=0,
                effective_qty=0,
                counted_qty=0,
                variance_qty=0,
                status="OK",
            )
            db.add(oi)
            db.flush()

        # Update counted qty with NEW tags only
        oi.counted_qty = float(oi.counted_qty or 0) + count

        # Compute movement since snapshot
        movement_qty = compute_movement_qty_for_item(db, session, item_id)
        oi.movement_qty = movement_qty

        # Effective qty = snapshot + movement
        system_qty = float(oi.system_qty or 0)
        effective = system_qty + movement_qty
        oi.effective_qty = effective

        # Variance = counted − effective
        counted = float(oi.counted_qty or 0)
        oi.variance_qty = counted - effective

        # Determine status
        if oi.variance_qty == 0:
            oi.status = "OK"
        elif oi.variance_qty > 0:
            oi.status = "OVER"
        else:
            oi.status = "SHORT"

        # Variance value (if cost available)
        item = db.query(models.Item).get(item_id)
        cost = float(item.cost_price or 0) if item else 0
        oi.variance_value = oi.variance_qty * cost

    # ================================
    # Update session progress
    # ================================
    scanned_item_count = (
        db.query(models.StockOpnameItem)
        .filter(
            models.StockOpnameItem.session_id == session_id,
            models.StockOpnameItem.counted_qty > 0,
        )
        .count()
    )

    session.items_scanned = scanned_item_count
    session.progress_percent = (
        scanned_item_count * 100.0 / session.total_items
        if session.total_items else 0
    )

    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return session


# ==============================
# Create Inventory Movement
# ==============================
def create_inventory_movement(db: Session, payload: schemas.InventoryMovementCreate):
    movement = models.InventoryMovement(
        item_id=payload.item_id,
        location_id=payload.location_id,
        qty_change=payload.qty_change,
        reason=payload.reason,
        reference_id=payload.reference_id,
    )

    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


def get_opname_items_with_item_info(
    db: Session,
    session_id: int,
    status: str | None = None,
):
    q = (
        db.query(
            models.StockOpnameItem.item_id,
            models.Item.sku,
            models.Item.name,
            models.StockOpnameItem.system_qty,
            models.StockOpnameItem.movement_qty,
            models.StockOpnameItem.effective_qty,
            models.StockOpnameItem.counted_qty,
            models.StockOpnameItem.variance_qty,
            models.StockOpnameItem.variance_value,
            models.StockOpnameItem.status,
        )
        .join(models.Item, models.Item.id == models.StockOpnameItem.item_id)
        .filter(models.StockOpnameItem.session_id == session_id)
    )

    if status:
        q = q.filter(models.StockOpnameItem.status == status)

    return q.order_by(models.Item.name.asc()).all()

def get_opname_items_with_item_and_rfid(
    db: Session,
    session_id: int,
    status: str | None = None,
):
    # Ambil data item opname + item info
    rows = (
        db.query(
            models.StockOpnameItem.item_id,
            models.Item.sku,
            models.Item.name,
            models.StockOpnameItem.system_qty,
            models.StockOpnameItem.movement_qty,
            models.StockOpnameItem.effective_qty,
            models.StockOpnameItem.counted_qty,
            models.StockOpnameItem.variance_qty,
            models.StockOpnameItem.variance_value,
            models.StockOpnameItem.status,
        )
        .join(models.Item, models.Item.id == models.StockOpnameItem.item_id)
        .filter(models.StockOpnameItem.session_id == session_id)
    )

    if status:
        rows = rows.filter(models.StockOpnameItem.status == status)

    rows = rows.all()

    # Ambil semua RFID untuk item-item tsb
    item_ids = [r.item_id for r in rows]

    rfid_rows = (
        db.query(models.RFIDTag.item_id, models.RFIDTag.tag_uid)
        .filter(models.RFIDTag.item_id.in_(item_ids))
        .filter(models.RFIDTag.status == "ACTIVE")
        .all()
    )

    # Group RFID per item_id
    rfid_map: dict[int, list[str]] = {}
    for item_id, tag_uid in rfid_rows:
        rfid_map.setdefault(item_id, []).append(tag_uid)

    # Gabungkan ke response
    result = []
    for r in rows:
        result.append(
            {
                "item_id": r.item_id,
                "sku": r.sku,
                "name": r.name,
                "system_qty": r.system_qty,
                "movement_qty": r.movement_qty,
                "effective_qty": r.effective_qty,
                "counted_qty": r.counted_qty,
                "variance_qty": r.variance_qty,
                "variance_value": r.variance_value,
                "status": r.status,
                "item_codes": rfid_map.get(r.item_id, []),
            }
        )

    return result