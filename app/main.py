from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Expense Tracker Starter", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
