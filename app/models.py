from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Enum,
    DateTime,
    Text,
    Integer,
    Numeric,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(150))
    created_at = Column(DateTime, default=datetime.utcnow)


class Location(Base):
    __tablename__ = "locations"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    code = Column(String(50), nullable=False, unique=True, index=True)
    type = Column(Enum("STORE", "WAREHOUSE", name="location_type"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)

    sessions = relationship("StockOpnameSession", back_populates="location")


class Item(Base):
    __tablename__ = "items"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    uom = Column(String(50), default="PCS")
    cost_price = Column(Numeric(15, 2), default=0)
    sell_price = Column(Numeric(15, 2), default=0)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)


class ItemLocation(Base):
    __tablename__ = "item_locations"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id"), nullable=False)
    system_qty = Column(Numeric(15, 3), default=0)


class RFIDTag(Base):
    __tablename__ = "rfid_tags"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    tag_uid = Column(String(64), unique=True, nullable=False, index=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id"))
    status = Column(
        Enum("ACTIVE", "LOST", "DAMAGED", name="rfid_status"),
        nullable=False,
        default="ACTIVE",
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)


class StockOpnameSession(Base):
    __tablename__ = "stock_opname_sessions"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    location_id = Column(BigInteger, ForeignKey("locations.id"), nullable=False)
    # waktu snapshot stok diambil
    snapshot_at = Column(DateTime)
    type = Column(Enum("FULL", "PARTIAL", name="opname_type"), nullable=False)
    status = Column(
        Enum("PLANNED", "IN_PROGRESS", "REVIEW", "CLOSED", name="opname_status"),
        nullable=False,
        default="PLANNED",
    )
    scheduled_start_at = Column(DateTime)
    scheduled_end_at = Column(DateTime)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    total_items = Column(Integer, default=0)
    items_scanned = Column(Integer, default=0)
    progress_percent = Column(Numeric(5, 2), default=0)
    notes = Column(Text)
    created_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)

    location = relationship("Location", back_populates="sessions")
    items = relationship("StockOpnameItem", back_populates="session")


class StockOpnameItem(Base):
    __tablename__ = "stock_opname_items"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("stock_opname_sessions.id"), nullable=False)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)

    # snapshot stok saat sesi dibuat
    system_qty = Column(Numeric(15, 3), default=0)

    # pergerakan stok sejak snapshot (dari inventory_movements)
    movement_qty = Column(Numeric(15, 3), default=0)

    # qty teoritis final: system_qty + movement_qty
    effective_qty = Column(Numeric(15, 3), default=0)

    # hasil hitung RFID
    counted_qty = Column(Numeric(15, 3), default=0)

    # selisih counted vs effective
    variance_qty = Column(Numeric(15, 3), default=0)
    variance_value = Column(Numeric(18, 2), default=0)

    status = Column(Enum("OK", "OVER", "SHORT", name="opname_item_status"), default="OK")

    session = relationship("StockOpnameSession", back_populates="items")


class StockOpnameScan(Base):
    __tablename__ = "stock_opname_scans"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("stock_opname_sessions.id"), nullable=False)
    tag_uid = Column(String(64), nullable=False, index=True)
    item_id = Column(BigInteger, ForeignKey("items.id"))
    zone = Column(String(100))
    scanned_at = Column(DateTime, default=datetime.utcnow)
    scanned_by = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    item_id = Column(BigInteger, ForeignKey("items.id"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id"), nullable=False)
    qty_change = Column(Numeric(15, 3), nullable=False)
    reason = Column(
        Enum(
            "SALE",
            "RESTOCK",
            "TRANSFER_IN",
            "TRANSFER_OUT",
            "RETURN",
            "ADJUSTMENT",
            "CANCELLED",
            "OTHER",
            name="movement_reason",
        ),
        nullable=False,
    )
    reference_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    # optional relationships
    # item = relationship("Item")
    # location = relationship("Location")