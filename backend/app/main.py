from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — registers models on Base.metadata
from app.database import Base, engine
from app.routers import books, home, lessons

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LockedIn")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(lessons.router)
app.include_router(home.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
