"""에어코리아 시도별 실시간 측정정보."""
import httpx
from app.config import settings

BASE = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"

async def fetch_air(sido: str, station: str) -> dict:
    params = {
        "serviceKey": settings.airkorea_api_key, "returnType": "json",
        "numOfRows": 100, "pageNo": 1, "sidoName": sido, "ver": "1.3",
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(BASE, params=params)
        r.raise_for_status()
        items = r.json()["response"]["body"]["items"]
    match = next((it for it in items if it.get("stationName") == station), items[0] if items else {})
    def to_int(x):
        try: return int(x)
        except (TypeError, ValueError): return None
    return {
        "pm10": to_int(match.get("pm10Value")),
        "pm25": to_int(match.get("pm25Value")),
        "station": match.get("stationName"),
    }
