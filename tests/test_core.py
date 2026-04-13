"""순수 함수 단위 테스트."""
from datetime import datetime
from app.collectors.weather import _base_datetime, summarize
from app.decision import need_umbrella, need_mask

def test_base_datetime_picks_latest_slot():
    d, t = _base_datetime(datetime(2026, 4, 13, 10, 0))
    assert d == "20260413" and t == "0800"

def test_base_datetime_before_first_slot_uses_yesterday():
    d, t = _base_datetime(datetime(2026, 4, 13, 1, 0))
    assert d == "20260412" and t == "2300"

def test_summarize_buckets_am_pm():
    items = [
        {"category":"POP","fcstDate":"20260413","fcstTime":"0900","fcstValue":"30"},
        {"category":"POP","fcstDate":"20260413","fcstTime":"1500","fcstValue":"70"},
        {"category":"PCP","fcstDate":"20260413","fcstTime":"0900","fcstValue":"강수없음"},
        {"category":"PCP","fcstDate":"20260413","fcstTime":"1500","fcstValue":"2.5mm"},
        {"category":"TMP","fcstDate":"20260413","fcstTime":"0900","fcstValue":"12"},
        {"category":"TMP","fcstDate":"20260413","fcstTime":"1500","fcstValue":"19"},
    ]
    s = summarize(items, "20260413")
    assert s["am"]["pop_max"] == 30
    assert s["pm"]["pop_max"] == 70
    assert s["am"]["pcp_sum"] == 0.0
    assert s["pm"]["pcp_sum"] == 2.5
    assert s["am"]["tmp_min"] == 12 and s["pm"]["tmp_max"] == 19

def test_need_umbrella_high_prob():
    fc = {"am": {"pop_max": 80, "pcp_sum": 0}, "pm": {"pop_max": 30, "pcp_sum": 0}}
    needed, _ = need_umbrella(fc)
    assert needed is True

def test_need_umbrella_low():
    fc = {"am": {"pop_max": 20, "pcp_sum": 0}, "pm": {"pop_max": 10, "pcp_sum": 0}}
    needed, _ = need_umbrella(fc)
    assert needed is False

def test_need_mask_pm25_high():
    needed, msg = need_mask({"pm25": 50, "pm10": 70})
    assert needed is True and "PM2.5" in msg

def test_need_mask_clean():
    needed, _ = need_mask({"pm25": 10, "pm10": 20})
    assert needed is False
