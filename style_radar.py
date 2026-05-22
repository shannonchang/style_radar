"""
AI 穿搭靈感雷達 - 每週自動推播
來源 A：Pinterest CSV（手動匯出，放進 data/pinterest.csv）
來源 B：穿搭媒體 RSS（Hypebeast、Highsnobiety 等）
分析：Claude API
推播：Line Messaging API
"""

import os
import csv
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ──────────────────────────────────────────
# 設定區
# ──────────────────────────────────────────
CLAUDE_API_KEY     = os.environ["ANTHROPIC_API_KEY"]
LINE_CHANNEL_TOKEN = os.environ["LINE_CHANNEL_TOKEN"]
LINE_USER_ID       = os.environ["LINE_USER_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

FASHION_RSS = [
    ("Hypebeast",       "https://hypebeast.com/feed"),
    ("Highsnobiety",    "https://www.highsnobiety.com/feed/"),
    ("GQ",              "https://www.gq.com/feed/rss"),
    ("Put This On",     "https://putthison.com/feed/"),
    ("The Sartorialist","https://www.thesartorialist.com/feed/"),
]

STYLE_PREFERENCE = """
- clean fit
- relaxed fit / 鬆弛感
- 亞洲比例
- 韓系 / 日系
- NB 復古鞋
- 灰白黑色系
- 不喜歡：浮誇高街、過度 logo
"""


# ──────────────────────────────────────────
# 來源 A：Pinterest CSV
# ──────────────────────────────────────────
def load_pinterest_csv() -> list[dict]:
    csv_path = Path("data/pinterest.csv")
    if not csv_path.exists():
        print("  Pinterest CSV 不存在，跳過")
        return []

    pins = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pins.append({
                "source": "Pinterest",
                "title": row.get("Title", "").strip(),
                "note":  row.get("Note", "").strip(),
                "board": row.get("Board Name", "").strip(),
            })

    print(f"  讀到 {len(pins)} 筆")
    return pins


# ──────────────────────────────────────────
# 來源 B：穿搭媒體 RSS
# ──────────────────────────────────────────
def fetch_rss(name: str, url: str, max_items: int = 5) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)

        results = []
        for item in items[:max_items]:
            title = (
                item.findtext("title") or
                item.findtext("atom:title", namespaces=ns) or ""
            ).strip()
            desc = (
                item.findtext("description") or
                item.findtext("atom:summary", namespaces=ns) or ""
            ).strip()[:200]

            results.append({
                "source": name,
                "title":  title,
                "desc":   desc,
            })

        print(f"  ✅ {name}：{len(results)} 篇")
        return results

    except Exception as e:
        print(f"  ❌ {name}：{e}")
        return []


def collect_fashion_rss() -> list[dict]:
    all_items = []
    for name, url in FASHION_RSS:
        items = fetch_rss(name, url)
        all_items.extend(items)
    return all_items


# ──────────────────────────────────────────
# Claude 分析
# ──────────────────────────────────────────
def build_prompt(pinterest_pins: list[dict], rss_items: list[dict]) -> str:
    sections = []

    if pinterest_pins:
        lines = [f"- [{p['board']}] {p['title']} {p['note']}".strip()
                 for p in pinterest_pins]
        sections.append(f"【Pinterest 收藏 {len(pinterest_pins)} 張】\n" + "\n".join(lines))

    if rss_items:
        lines = [f"- [{i['source']}] {i['title']}" for i in rss_items]
        sections.append(f"【穿搭媒體本週文章 {len(rss_items)} 篇】\n" + "\n".join(lines))

    combined = "\n\n".join(sections) if sections else "（本週沒有任何資料）"

    return f"""你是亞洲穿搭顧問，同時熟悉男生和女生的穿搭趨勢。

我的風格偏好（男生視角）：
{STYLE_PREFERENCE}

以下是這週的穿搭資料：
{combined}

請用繁體中文回答，格式如下：

🎯 本週風格信號
（3 個本週最明顯的趨勢關鍵字，男女通用）

👨 男生穿搭建議
（根據本週資料，給一個具體的男生穿搭方向，
符合 clean fit / 亞洲比例，越實際越好）

👩 女生穿搭建議
（根據本週資料，給一個具體的女生穿搭方向，
同樣偏向簡約、亞洲比例，避免過度浮誇）

📰 值得關注
（從媒體文章挑 1 篇最值得看的，一句話說原因）

📐 本週色系傾向
（一句話）

語氣像朋友，不要像 AI 報告，200 字以內。"""


def analyze_with_claude(pinterest_pins: list[dict], rss_items: list[dict]) -> str:
    if not pinterest_pins and not rss_items:
        return "本週兩個來源都沒有資料，請確認 Pinterest CSV 是否放入 data/ 資料夾，以及網路連線是否正常。"

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": build_prompt(pinterest_pins, rss_items)}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


# ──────────────────────────────────────────
# Line 推播
# ──────────────────────────────────────────
def send_line(message: str, pinterest_count: int, rss_count: int):
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%m/%d")
    header = (
        f"👗 穿搭雷達週報 {today}\n"
        f"📌 Pinterest {pinterest_count} 張｜媒體 {rss_count} 篇\n"
        f"{'─' * 20}\n\n"
    )

    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": header + message}],
        },
        timeout=15,
    )
    resp.raise_for_status()
    print("Line 推播成功")


# ──────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────
def main():
    print("=== 穿搭雷達啟動 ===\n")

    print("[來源 A] Pinterest CSV")
    pinterest_pins = load_pinterest_csv()

    print("\n[來源 B] 穿搭媒體 RSS")
    rss_items = collect_fashion_rss()

    print(f"\n合計：Pinterest {len(pinterest_pins)} 筆｜媒體 {len(rss_items)} 篇")

    print("\nClaude 分析中...")
    analysis = analyze_with_claude(pinterest_pins, rss_items)
    print(f"\n{analysis}")

    print("\n推播到 Line...")
    send_line(analysis, len(pinterest_pins), len(rss_items))

    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()