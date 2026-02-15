import asyncio

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..models import GlobalPageAnalysis, PageAnalysis, SectionPageAnalysisResult
from ..services import analysis_store, global_analysis_store, job_store, section_analysis_store
from ..services.analysis_pipeline import run_analysis
from ..services.global_analysis_pipeline import run_global_analysis
from ..services.section_analysis_pipeline import run_section_analysis
from ..services.section_instructions import (
    get_raw_section_instructions,
    list_all_sections,
    save_section_instructions,
    delete_section_instructions,
)
from ..services.section_chat import chat_with_section

router = APIRouter(prefix="/api")


@router.post("/jobs/{job_id}/compare", status_code=202)
async def start_comparison(job_id: str, mode: str = Query(default="paired")) -> dict:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.analysis_status == "running":
        raise HTTPException(status_code=409, detail="Analysis already running")

    asyncio.create_task(run_analysis(job_id, mode=mode))
    return {"status": "started", "job_id": job_id}


@router.get("/jobs/{job_id}/pairs/{pair_id}/sections")
async def get_sections(
    job_id: str,
    pair_id: str,
    page: int = Query(...),
    category: str = Query(default="reference"),
) -> PageAnalysis | None:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not any(p.pair_id == pair_id for p in job.pairs):
        raise HTTPException(status_code=404, detail="Pair not found")
    if category not in ("reference", "test"):
        raise HTTPException(status_code=400, detail="Invalid category")

    return analysis_store.get(job_id, pair_id, category, page)


@router.post("/jobs/{job_id}/global-analyze", status_code=202)
async def start_global_analysis(job_id: str) -> dict:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.global_analysis_status == "running":
        raise HTTPException(status_code=409, detail="Global analysis already running")

    asyncio.create_task(run_global_analysis(job_id))
    return {"status": "started", "job_id": job_id}


@router.get("/jobs/{job_id}/pairs/{pair_id}/global")
async def get_global_analysis(
    job_id: str,
    pair_id: str,
    page: int = Query(...),
) -> GlobalPageAnalysis | None:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not any(p.pair_id == pair_id for p in job.pairs):
        raise HTTPException(status_code=404, detail="Pair not found")

    return global_analysis_store.get(job_id, pair_id, page)


# --- Section analysis ---


@router.post("/jobs/{job_id}/section-analyze", status_code=202)
async def start_section_analysis(job_id: str) -> dict:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.analysis_status != "done":
        raise HTTPException(status_code=409, detail="Section detection must complete first")
    if job.section_analysis_status == "running":
        raise HTTPException(status_code=409, detail="Section analysis already running")

    asyncio.create_task(run_section_analysis(job_id))
    return {"status": "started", "job_id": job_id}


@router.get("/jobs/{job_id}/pairs/{pair_id}/section-results")
async def get_section_results(
    job_id: str,
    pair_id: str,
    page: int = Query(...),
) -> SectionPageAnalysisResult | None:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not any(p.pair_id == pair_id for p in job.pairs):
        raise HTTPException(status_code=404, detail="Pair not found")

    return section_analysis_store.get(job_id, pair_id, page)


# --- Section instructions CRUD ---


@router.get("/section-instructions")
async def list_section_instructions() -> dict[str, str]:
    return list_all_sections()


@router.get("/section-instructions/{section_name}")
async def get_section_instructions(section_name: str) -> dict:
    return get_raw_section_instructions(section_name)


class SectionChatRequest(BaseModel):
    section_name: str
    page: int
    message: str


class InstructionBody(BaseModel):
    instructions: str


@router.put("/section-instructions/{section_name}")
async def put_section_instructions(section_name: str, body: InstructionBody) -> dict:
    save_section_instructions(section_name, body.instructions)
    return {"status": "saved", "section_name": section_name}


@router.post("/jobs/{job_id}/pairs/{pair_id}/section-chat")
async def section_chat(job_id: str, pair_id: str, body: SectionChatRequest) -> dict:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    pair = next((p for p in job.pairs if p.pair_id == pair_id), None)
    if not pair:
        raise HTTPException(status_code=404, detail="Pair not found")

    response_text = await chat_with_section(
        job_id, pair_id, pair.filename,
        body.section_name, body.page, body.message,
    )
    return {"response": response_text}


@router.delete("/section-instructions/{section_name}")
async def remove_section_instructions(section_name: str) -> dict:
    deleted = delete_section_instructions(section_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Section not found")
    return {"status": "deleted", "section_name": section_name}
