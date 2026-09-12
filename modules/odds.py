from __future__ import annotations
import html as _html
import json
import re
from urllib.request import Request, urlopen
import pandas as pd

JRA_VENUE_CODES = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
    "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
}


def normalize_yyyymmdd(value):
    if value is None: return None
    try:
        if pd.isna(value): return None
    except Exception: pass
    text = re.sub(r"\D", "", str(value))
    if len(text) >= 8: return text[:8]
    try: return f"{int(float(value)):08d}"
    except Exception: return None


def _decode(raw: bytes, content_type: str = "") -> str:
    for enc in ("utf-8", "cp932", "shift_jis", "euc-jp"):
        try: return raw.decode(enc)
        except Exception: pass
    return raw.decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S|re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", _html.unescape(text))


def fetch_meeting_info(yyyymmdd: str) -> tuple[dict, list[str]]:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return {}, ["開催日を判定できませんでした"]
    y, m, md = yyyymmdd[:4], int(yyyymmdd[4:6]), yyyymmdd[4:8]
    url = f"https://www.jra.go.jp/keiba/calendar{y}/{y}/{m}/{md}.html"
    headers = {"User-Agent":"Mozilla/5.0", "Accept-Language":"ja,en-US;q=0.8"}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            plain = _strip_html(_decode(resp.read(), resp.headers.get("Content-Type", "")))
        meetings = {}
        for kai, venue, day in re.findall(r"(\d+)回\s*(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)\s*(\d+)日", plain):
            meetings[venue] = {"kai": int(kai), "day": int(day)}
        return meetings, ([] if meetings else [f"開催情報を抽出できませんでした: {url}"])
    except Exception as e:
        return {}, [f"開催情報取得失敗: {e}"]


def make_race_id(place: str, yyyymmdd: str, kai: int, day: int, race_no: int) -> str | None:
    code = JRA_VENUE_CODES.get(str(place).strip())
    if not code or not yyyymmdd or len(yyyymmdd) != 8: return None
    return f"{yyyymmdd[:4]}{code}{int(kai):02d}{int(day):02d}{int(race_no):02d}"


def extract_win_odds(payload: dict, horses: list[dict]) -> dict:
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: data = {}
    odds_root = data.get("odds", {}) if isinstance(data, dict) else {}
    win = odds_root.get("1", {}) if isinstance(odds_root, dict) else {}
    if not isinstance(win, dict): return {}
    names = {int(h["horse_no"]): str(h.get("horse_name", "")) for h in horses if h.get("horse_no") is not None}
    out = {}
    for k, values in win.items():
        try: no = int(str(k))
        except Exception: continue
        if not isinstance(values, (list, tuple)) or not values: continue
        raw = str(values[0]).strip()
        if not re.fullmatch(r"\d+(?:\.\d+)?", raw): continue
        pop = None
        if len(values) >= 3:
            try: pop = int(str(values[2]).strip())
            except Exception: pass
        out[no] = {"horse_no": no, "horse_name": names.get(no, ""), "odds": float(raw), "popularity": pop}
    return out


def fetch_win_odds(date, place: str, race_no: int, horses: list[dict], force_update: bool=False) -> tuple[dict, list[str]]:
    ymd = normalize_yyyymmdd(date)
    meetings, errs = fetch_meeting_info(ymd)
    meet = meetings.get(str(place).strip())
    if not meet:
        return {}, errs + [f"{place}の回次・日次を取得できませんでした"]
    race_id = make_race_id(place, ymd, meet["kai"], meet["day"], race_no)
    if not race_id: return {}, errs + ["race_idを生成できませんでした"]
    action = "update" if force_update else "init"
    api_url = f"https://race.netkeiba.com/api/api_get_jra_odds.html?race_id={race_id}&type=1&action={action}&sort=odds&compress=0&output=json"
    headers = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        "Accept":"application/json, text/javascript, */*; q=0.01",
        "Referer": f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}",
    }
    try:
        req = Request(api_url, headers=headers)
        with urlopen(req, timeout=10) as resp: text = resp.read().decode("utf-8", errors="replace").strip()
        if not text.startswith("{"):
            m = re.search(r"\((\{.*\})\)\s*;?\s*$", text, flags=re.S)
            if m: text = m.group(1)
        payload = json.loads(text)
        odds = extract_win_odds(payload, horses)
        return odds, errs
    except Exception as e:
        return {}, errs + [f"単勝オッズ取得失敗: {e}"]
