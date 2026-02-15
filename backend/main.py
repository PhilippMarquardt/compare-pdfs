from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analysis, jobs

app = FastAPI(title="PDF Compare API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(analysis.router)
