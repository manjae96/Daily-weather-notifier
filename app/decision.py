"""우산/마스크 판단 로직."""
from app.config import settings

def need_umbrella(forecast: dict) -> tuple[bool, str]:
    pop = max(forecast["am"]["pop_max"], forecast["pm"]["pop_max"])
    pcp = forecast["am"]["pcp_sum"] + forecast["pm"]["pcp_sum"]
    if pop >= settings.rain_prob_threshold or pcp >= settings.rain_mm_threshold:
        return True, f"강수확률 최대 {pop}%, 예상 강수량 {pcp:.1f}mm"
    return False, f"강수확률 최대 {pop}%, 강수량 미미"

def need_mask(air: dict) -> tuple[bool, str]:
    pm25 = air.get("pm25"); pm10 = air.get("pm10")
    triggers = []
    if pm25 is not None and pm25 >= settings.pm25_threshold:
        triggers.append(f"PM2.5 {pm25}㎍/㎥")
    if pm10 is not None and pm10 >= settings.pm10_threshold:
        triggers.append(f"PM10 {pm10}㎍/㎥")
    if triggers:
        return True, " / ".join(triggers) + " — 마스크 권장"
    return False, f"PM2.5 {pm25}, PM10 {pm10} — 양호"
