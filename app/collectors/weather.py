"""기상청 단기예보(getVilageFcst) 수집기."""
from datetime import datetime, timedelta
import httpx
from app.config import settings

BASE = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

def _base_datetime(now: datetime) -> tuple[str, str]:
    slots = [2, 5, 8, 11, 14, 17, 20, 23]
    candidates = [s for s in slots if s <= now.hour]
    if not candidates:
        d = now - timedelta(days=1)
        h = 23
    else:
        d, h = now, max(candidates)
    return d.strftime("%Y%m%d"), f"{h:02d}00"

async def fetch_forecast(nx: int, ny: int, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    base_date, base_time = _base_datetime(now)
    params = {
        "serviceKey": settings.kma_api_key, "pageNo": 1, "numOfRows": 1000,
        "dataType": "JSON", "base_date": base_date, "base_time": base_time,
        "nx": nx, "ny": ny,
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(BASE, params=params)
        r.raise_for_status()
        items = r.json()["response"]["body"]["items"]["item"]
    return summarize(items, now.strftime("%Y%m%d"))

def summarize(items: list[dict], target_date: str) -> dict:
    """오전(06-12) / 오후(12-18) 강수확률·강수량·기온 집계."""
    am = {"pop": [], "pcp": [], "tmp": []}
    pm = {"pop": [], "pcp": [], "tmp": []}
    for it in items:
        if it["fcstDate"] != target_date:
            continue
        h = int(it["fcstTime"][:2])
        bucket = am if 6 <= h < 12 else (pm if 12 <= h < 18 else None)
        if bucket is None:
            continue
        v = it["fcstValue"]
        if it["category"] == "POP":
            bucket["pop"].append(int(v))
        elif it["category"] == "PCP":
            if v in ("강수없음", "-", ""):
                bucket["pcp"].append(0.0)
            else:
                num = "".join(ch for ch in str(v) if ch.isdigit() or ch == ".")
                bucket["pcp"].append(float(num) if num else 0.0)
        elif it["category"] == "TMP":
            bucket["tmp"].append(float(v))

    def agg(b):
        return {
            "pop_max": max(b["pop"], default=0),
            "pcp_sum": round(sum(b["pcp"]), 1),
            "tmp_min": min(b["tmp"], default=None),
            "tmp_max": max(b["tmp"], default=None),
        }
    return {"am": agg(am), "pm": agg(pm)}
