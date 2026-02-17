from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analysis, jobs

app = FastAPI(title="PDF Compare API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:30097",
        "http://localhost:30098",
        "http://localhost:30099",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(analysis.router)
