"""매일 아침 실행되는 메인 잡: 수집 → 판단 → RAG 보강 → 알림."""
import asyncio
from app.config import settings
from app.collectors.weather import fetch_forecast
from app.collectors.air_quality import fetch_air
from app.decision import need_umbrella, need_mask
from app.llm.client import get_client
from app.rag.store import retrieve
from app.notifier.sender import get_notifier

SYSTEM_PROMPT = (
    "당신은 한국 사용자에게 아침 날씨 브리핑을 제공하는 친절한 비서입니다. "
    "주어진 컨텍스트(옷차림/건강/교통 가이드)와 오늘의 데이터를 종합해, "
    "마곡·선릉·미아사거리 출근자에게 도움이 되는 2~3문장 조언을 한국어로 작성하세요."
)

async def collect_region(name: str, info: dict) -> dict:
    fc = await fetch_forecast(info["nx"], info["ny"])
    air = await fetch_air(info["sido"], info["station"])
    umb, umb_reason = need_umbrella(fc)
    mask, mask_reason = need_mask(air)
    return {"name": name, "fc": fc, "air": air,
            "umbrella": umb, "umb_reason": umb_reason,
            "mask": mask, "mask_reason": mask_reason}

def format_brief(rs: list[dict], advice: str) -> str:
    lines = ["☀️ *오늘의 출근 브리핑*\n"]
    for r in rs:
        am, pm = r["fc"]["am"], r["fc"]["pm"]
        lines.append(f"📍 *{r['name']}*")
        lines.append(f"  오전 {am['tmp_min']}~{am['tmp_max']}°C, 강수확률 {am['pop_max']}%, {am['pcp_sum']}mm")
        lines.append(f"  오후 {pm['tmp_min']}~{pm['tmp_max']}°C, 강수확률 {pm['pop_max']}%, {pm['pcp_sum']}mm")
        lines.append(f"  ☂️ {'필요' if r['umbrella'] else '불필요'} ({r['umb_reason']})")
        lines.append(f"  😷 {'권장' if r['mask'] else '불필요'} ({r['mask_reason']})\n")
    lines.append("💡 *조언*\n" + advice)
    return "\n".join(lines)

async def run() -> str:
    results = await asyncio.gather(*[collect_region(n, i) for n, i in settings.regions.items()])
    summary = "\n".join(
        f"{r['name']}: 우산={r['umbrella']}({r['umb_reason']}), 마스크={r['mask']}({r['mask_reason']})"
        for r in results
    )
    try:
        ctx = await retrieve(summary, top_k=3)
        ctx_text = "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in ctx)
    except Exception as e:
        ctx_text = f"(RAG 미적용: {e})"
    llm = get_client()
    advice = await llm.generate(SYSTEM_PROMPT, f"# 컨텍스트\n{ctx_text}\n\n# 오늘 요약\n{summary}")
    msg = format_brief(results, advice)
    await get_notifier().send(msg)
    return msg

if __name__ == "__main__":
    asyncio.run(run())
