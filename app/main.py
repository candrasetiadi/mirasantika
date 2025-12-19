from fastapi import FastAPI
from .database import engine, Base
from .routers import stock_opname, inventory_movements
from fastapi.middleware.cors import CORSMiddleware


# untuk dev: auto create table jika belum ada
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Stock Opname RFID API",
    version="0.2.0",
)

# =========================
# CORS CONFIGURATION
# =========================
app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stock_opname.router)
app.include_router(inventory_movements.router)


@app.get("/")
def read_root():
    return {"message": "Smart Stock Opname RFID API is running"}