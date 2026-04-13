"""FastAPI 엔트리. 헬스체크 + 수동 트리거 + 오늘 조회."""
from fastapi import FastAPI, HTTPException
from app.jobs.morning_brief import run, collect_region
from app.config import settings
from app.rag.store import ingest_directory

app = FastAPI(title="Daily Weather Notifier")

@app.get("/health")
async def health(): return {"status": "ok"}

@app.get("/today/{region}")
async def today(region: str):
    info = settings.regions.get(region)
    if not info:
        raise HTTPException(404, f"Unknown region: {region}")
    return await collect_region(region, info)

@app.post("/trigger/morning-brief")
async def trigger():
    msg = await run()
    return {"sent": True, "message": msg}

@app.post("/rag/ingest")
async def ingest():
    n = await ingest_directory()
    return {"chunks_indexed": n}
