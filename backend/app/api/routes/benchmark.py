"""Benchmark endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import BenchmarkResponseSchema
from app.benchmark.runner import run_benchmark
from app.core.database import get_db

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("", response_model=BenchmarkResponseSchema)
def get_benchmark(db: Session = Depends(get_db)) -> BenchmarkResponseSchema:
    """Run the full benchmark evaluation and return precision/recall/F1/throughput."""
    result = run_benchmark(db)
    return BenchmarkResponseSchema(**result)
