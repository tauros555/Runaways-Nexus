from __future__ import annotations

import html as html_lib
import re
from urllib.request import Request, urlopen

import streamlit as st

JRA_BABA_URLS = [
    "https://www.jra.go.jp/keiba/baba/index.html",
    "https://www.jra.go.jp/keiba/baba/index2.html",
    "https://www.jra.go.jp/keiba/baba/index3.html",
]


def _strip_html(raw):
    if raw is None:
        return ""
    text = re.sub(r"<script\b.*?</script>", " ", str(raw), flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_jra_response(raw_bytes, content_type=""):
    candidates = []
    m = re.search(r"charset=([\w\-]+)", content_type or "", flags=re.I)
    if m:
        candidates.append(m.group(1))
    candidates += ["utf-8", "cp932", "shift_jis"]
    for enc in candidates:
        try:
            return raw_bytes.decode(enc)
        except Exception:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _parse_jra_baba_page(page_html, url):
    plain = _strip_html(page_html)
    venue = None
    for pat in [
        r"馬場情報[（(]\s*([^）)]+?)競馬場\s*[）)]",
        r"([^\s]+?)競馬場\s+馬場情報",
    ]:
        m = re.search(pat, plain)
        if m:
            venue = m.group(1).strip()
            break

    cushion_time = None
    m = re.search(
        r'id=["\']cushion_list["\'][^>]*>\s*<option[^>]*>(.*?)</option>',
        page_html,
        flags=re.I | re.S,
    )
    if m:
        cushion_time = _strip_html(m.group(1)) or None

    turf_going = None
    dirt_going = None
    status_match = re.search(r"馬場状態(.*?)芝のクッション値", plain, flags=re.S)
    status_text = status_match.group(1) if status_match else plain
    m = re.search(r"芝\s*(良|稍重|重|不良).*?ダート\s*(良|稍重|重|不良)", status_text, flags=re.S)
    if m:
        turf_going, dirt_going = m.group(1), m.group(2)

    status_time = None
    m = re.search(r"馬場状態[（(]([^）)]+?現在)[）)]", plain)
    if m:
        status_time = m.group(1).strip()

    return {
        "venue": venue,
        "cushion": None,  # 実測値は描画後DOMから取得
        "cushion_time": cushion_time,
        "turf_going": turf_going,
        "dirt_going": dirt_going,
        "status_time": status_time,
        "url": url,
    }


def _fetch_rendered_values(urls):
    rendered = {}
    errors = []
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--lang=ja-JP")
        options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36")

        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 15)
        for url in urls:
            try:
                driver.get(url)
                value_el = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#cushion_num p strong")))
                time_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#cushion_list option:first-child")))
                value_text = value_el.text.strip()
                time_text = time_el.text.strip()
                body_text = driver.find_element(By.TAG_NAME, "body").text

                venue = None
                m = re.search(r"馬場情報[（(]\s*([^）)]+?)競馬場\s*[）)]", body_text)
                if not m:
                    m = re.search(r"(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)競馬場", body_text)
                if m:
                    venue = m.group(1).strip()

                turf_going = None
                dirt_going = None
                for selector, target in [("#turf_info", "turf"), ("#dirt_info", "dirt")]:
                    try:
                        txt = driver.find_element(By.CSS_SELECTOR, selector).text
                        gm = re.search(r"(良|稍重|重|不良)", txt)
                        if gm:
                            if target == "turf":
                                turf_going = gm.group(1)
                            else:
                                dirt_going = gm.group(1)
                    except Exception:
                        pass

                if turf_going is None or dirt_going is None:
                    sm = re.search(
                        r"馬場状態.*?芝\s*(良|稍重|重|不良).*?ダート\s*(良|稍重|重|不良)",
                        body_text,
                        flags=re.S,
                    )
                    if sm:
                        turf_going = turf_going or sm.group(1)
                        dirt_going = dirt_going or sm.group(2)

                if venue and re.fullmatch(r"\d+(?:\.\d+)?", value_text):
                    rendered[venue] = {
                        "cushion": float(value_text),
                        "cushion_time": time_text or None,
                        "turf_going": turf_going,
                        "dirt_going": dirt_going,
                    }
                else:
                    errors.append(f"{url}: クッション実測値を判定できませんでした ({value_text!r})")
            except Exception as e:
                errors.append(f"{url}: ブラウザ取得失敗 - {e}")
    except Exception as e:
        errors.append(f"Chromium/Seleniumを起動できませんでした - {e}")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return rendered, errors


@st.cache_data(ttl=300, show_spinner=False)
def fetch_jra_track_conditions():
    results = {}
    errors = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
    for url in JRA_BABA_URLS:
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=8) as resp:
                raw = resp.read()
                page_html = _decode_jra_response(raw, resp.headers.get("Content-Type", ""))
            info = _parse_jra_baba_page(page_html, url)
            if info.get("venue"):
                results[info["venue"]] = info
        except Exception as e:
            errors.append(f"{url}: {e}")

    rendered, rendered_errors = _fetch_rendered_values(JRA_BABA_URLS)
    errors.extend(rendered_errors)
    for venue, info in rendered.items():
        results.setdefault(venue, {"venue": venue})
        results[venue].update({k: v for k, v in info.items() if v is not None})
    return results, errors


def cushion_to_nexus_band(value: float | None) -> str | None:
    """2020-2026クッション履歴の概ね3分位に合わせたNexus 3帯。"""
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if v <= 9.0:
        return "低"
    if v >= 9.6:
        return "高"
    return "中"
