from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..models import JobMetadata
from ..services import job_store

router = APIRouter(prefix="/api")

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"


@router.post("/jobs", response_model=JobMetadata, status_code=201)
async def create_job(
    reference_files: list[UploadFile] = File(...),
    test_files: list[UploadFile] = File(...),
    report_type: str = Form(default="none"),
) -> JobMetadata:
    job_id = uuid4().hex[:12]

    reference_dir = UPLOADS_DIR / job_id / "reference"
    test_dir = UPLOADS_DIR / job_id / "test"
    reference_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    reference_filenames: list[str] = []
    for upload in reference_files:
        filename = upload.filename or "unknown.pdf"
        dest = reference_dir / filename
        content = await upload.read()
        dest.write_bytes(content)
        reference_filenames.append(filename)

    test_filenames: list[str] = []
    for upload in test_files:
        filename = upload.filename or "unknown.pdf"
        dest = test_dir / filename
        content = await upload.read()
        dest.write_bytes(content)
        test_filenames.append(filename)

    job = job_store.create_job(
        job_id=job_id,
        report_type=report_type,
        reference_dir=str(reference_dir),
        test_dir=str(test_dir),
        reference_filenames=reference_filenames,
        test_filenames=test_filenames,
    )

    return job


@router.get("/jobs/{job_id}", response_model=JobMetadata)
async def get_job(job_id: str) -> JobMetadata:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/files/{category}/{filename}")
async def get_file(job_id: str, category: str, filename: str) -> FileResponse:
    if category not in ("reference", "test"):
        raise HTTPException(status_code=404, detail="Invalid category")

    file_path = UPLOADS_DIR / job_id / category / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(file_path), media_type="application/pdf")
