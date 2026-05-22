"""
AI 穿搭靈感雷達 - 每週自動推播
來源 A：Pinterest CSV（手動匯出，放進 data/pinterest.csv）
來源 B：穿搭媒體 RSS（Hypebeast、Highsnobiety 等）
圖片：Unsplash API（真實照）+ DALL-E 3（AI 生成）
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
CLAUDE_API_KEY      = os.environ["ANTHROPIC_API_KEY"]
LINE_CHANNEL_TOKEN  = os.environ["LINE_CHANNEL_TOKEN"]
LINE_USER_ID        = os.environ["LINE_USER_ID"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]
OPENAI_API_KEY      = os.environ["OPENAI_API_KEY"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

FASHION_RSS = [
    ("Hypebeast",    "https://hypebeast.com/feed"),
    ("Highsnobiety", "https://www.highsnobiety.com/feed/"),
    ("GQ",           "https://www.gq.com/feed/rss"),
    ("Put This On",  "https://putthison.com/feed/"),
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

FALLBACK_QUERIES = {
    "male":   ["minimal menswear outfit", "clean fit streetwear", "korean fashion men"],
    "female": ["minimal womenswear outfit", "clean fit women fashion", "korean fashion women"],
}


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
            results.append({"source": name, "title": title, "desc": desc})

        print(f"  ✅ {name}：{len(results)} 篇")
        return results

    except Exception as e:
        print(f"  ❌ {name}：{e}")
        return []


def collect_fashion_rss() -> list[dict]:
    all_items = []
    for name, url in FASHION_RSS:
        all_items.extend(fetch_rss(name, url))
    return all_items


# ──────────────────────────────────────────
# Unsplash：真實穿搭照
# ──────────────────────────────────────────
def fetch_unsplash_image(query: str, gender: str = "") -> str | None:
    queries = [query]
    if gender in FALLBACK_QUERIES:
        queries += FALLBACK_QUERIES[gender]

    for q in queries:
        try:
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
                params={
                    "query": q,
                    "per_page": 5,
                    "orientation": "portrait",
                    "content_filter": "high",
                },
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                url = results[0]["urls"]["regular"]
                print(f"  ✅ Unsplash「{q}」→ 取得圖片")
                return url
            print(f"  ⚠️ 搜尋「{q}」無結果，嘗試備用...")
        except Exception as e:
            print(f"  ❌ Unsplash 失敗：{e}")
            break

    print("  ❌ Unsplash 所有關鍵字都無結果")
    return None


# ──────────────────────────────────────────
# DALL-E 3：AI 生成穿搭示意圖
# ──────────────────────────────────────────
def generate_dalle_image(dalle_prompt: str) -> str | None:
    try:
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": dalle_prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
            },
            timeout=60,
            allow_redirects=False,
        )
        # 如果收到 redirect，手動處理
        if resp.status_code in (301, 302, 307, 308):
            location = resp.headers.get("Location", "")
            print(f"  ⚠️ Redirect 到：{location}")
            resp = requests.post(
                location,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "dall-e-3",
                    "prompt": dalle_prompt,
                    "n": 1,
                    "size": "1024x1024",
                    "quality": "standard",
                },
                timeout=60,
            )
        resp.raise_for_status()
        url = resp.json()["data"][0]["url"]
        print(f"  ✅ DALL-E 3 生成成功")
        return url
    except Exception as e:
        print(f"  ❌ DALL-E 3 失敗：{e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"  ❌ 錯誤內容：{e.response.text}")
        return None


def build_dalle_prompt(gender: str, style_desc: str) -> str:
    """把 Claude 分析出的風格描述轉成 DALL-E prompt"""
    if gender == "male":
        return (
            f"Fashion lookbook photo of an Asian male model wearing {style_desc}. "
            "Clean minimal background, studio lighting, full body shot showing outfit proportions. "
            "Korean street fashion aesthetic, clean fit, relaxed silhouette. "
            "High quality fashion photography, no text, no watermark."
        )
    else:
        return (
            f"Fashion lookbook photo of an Asian female model wearing {style_desc}. "
            "Clean minimal background, studio lighting, full body shot showing outfit proportions. "
            "Korean minimal fashion aesthetic, simple and elegant. "
            "High quality fashion photography, no text, no watermark."
        )


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
（具體的男生穿搭方向，符合 clean fit / 亞洲比例）

👩 女生穿搭建議
（具體的女生穿搭方向，偏向簡約、亞洲比例）

📰 值得關注
（從媒體文章挑 1 篇最值得看的，一句話說原因）

📐 本週色系傾向
（一句話）

---
最後在回答最末尾，另起一行加上以下四行（供圖片生成使用，不要給用戶看）：
MALE_QUERY: [3-5個英文關鍵字，給 Unsplash 搜尋真實穿搭照]
FEMALE_QUERY: [3-5個英文關鍵字，給 Unsplash 搜尋真實穿搭照]
MALE_DALLE: [10-15個英文單字，描述男生本週穿搭的具體單品和顏色，給 DALL-E 生成圖用]
FEMALE_DALLE: [10-15個英文單字，描述女生本週穿搭的具體單品和顏色，給 DALL-E 生成圖用]

語氣像朋友，不要像 AI 報告，200 字以內。"""


def parse_analysis(raw: str) -> tuple[str, str, str, str, str]:
    """拆出主要分析文字、Unsplash 關鍵字、DALL-E prompt"""
    male_query   = "korean minimal menswear clean fit"
    female_query = "minimal womenswear neutral outfit"
    male_dalle   = "oversized linen shirt wide pants white sneakers minimal korean menswear"
    female_dalle = "linen dress neutral tones minimal korean womenswear simple elegant"

    for line in raw.splitlines():
        if line.startswith("MALE_QUERY:"):
            male_query = line.replace("MALE_QUERY:", "").strip()
        elif line.startswith("FEMALE_QUERY:"):
            female_query = line.replace("FEMALE_QUERY:", "").strip()
        elif line.startswith("MALE_DALLE:"):
            male_dalle = line.replace("MALE_DALLE:", "").strip()
        elif line.startswith("FEMALE_DALLE:"):
            female_dalle = line.replace("FEMALE_DALLE:", "").strip()

    main_text = "\n".join(
        line for line in raw.splitlines()
        if not any(line.startswith(k) for k in
                   ["MALE_QUERY:", "FEMALE_QUERY:", "MALE_DALLE:", "FEMALE_DALLE:", "---"])
    ).strip()

    return main_text, male_query, female_query, male_dalle, female_dalle


def analyze_with_claude(pinterest_pins: list[dict], rss_items: list[dict]):
    if not pinterest_pins and not rss_items:
        return "本週兩個來源都沒有資料，請確認 Pinterest CSV 是否放入 data/ 資料夾。", "", "", "", ""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 700,
            "messages": [{"role": "user", "content": build_prompt(pinterest_pins, rss_items)}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["content"][0]["text"]
    return parse_analysis(raw)


# ──────────────────────────────────────────
# Line 推播
# ──────────────────────────────────────────
def build_line_messages(
    analysis: str,
    pinterest_count: int,
    rss_count: int,
    male_unsplash: str | None,
    female_unsplash: str | None,
    male_dalle: str | None,
    female_dalle: str | None,
) -> list[dict]:
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%m/%d")
    header = (
        f"👗 穿搭雷達週報 {today}\n"
        f"📌 Pinterest {pinterest_count} 張｜媒體 {rss_count} 篇\n"
        f"{'─' * 20}\n\n"
    )

    messages = [{"type": "text", "text": header + analysis}]

    def add_image(url: str, caption: str):
        messages.append({
            "type": "image",
            "originalContentUrl": url,
            "previewImageUrl":    url,
        })
        messages.append({"type": "text", "text": caption})

    # 男生圖片
    if male_unsplash or male_dalle:
        messages.append({"type": "text", "text": "── 👨 男生參考圖 ──"})
        if male_unsplash:
            add_image(male_unsplash, "📷 真實穿搭參考（Unsplash）")
        if male_dalle:
            add_image(male_dalle, "🎨 AI 風格示意圖（DALL-E 3）")

    # 女生圖片
    if female_unsplash or female_dalle:
        messages.append({"type": "text", "text": "── 👩 女生參考圖 ──"})
        if female_unsplash:
            add_image(female_unsplash, "📷 真實穿搭參考（Unsplash）")
        if female_dalle:
            add_image(female_dalle, "🎨 AI 風格示意圖（DALL-E 3）")

    return messages


def send_line(messages: list[dict]):
    chunks = [messages[i:i+5] for i in range(0, len(messages), 5)]
    for chunk in chunks:
        resp = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"to": LINE_USER_ID, "messages": chunk},
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
    analysis, male_query, female_query, male_dalle_desc, female_dalle_desc = \
        analyze_with_claude(pinterest_pins, rss_items)
    print(f"\n{analysis}")
    print(f"\nUnsplash 關鍵字 → 男：{male_query}｜女：{female_query}")
    print(f"DALL-E 描述 → 男：{male_dalle_desc}｜女：{female_dalle_desc}")

    print("\n[圖片] Unsplash 搜尋...")
    male_unsplash   = fetch_unsplash_image(male_query,   gender="male")
    female_unsplash = fetch_unsplash_image(female_query, gender="female")

    print("\n[圖片] DALL-E 3 生成...")
    male_ai   = generate_dalle_image(build_dalle_prompt("male",   male_dalle_desc))
    female_ai = generate_dalle_image(build_dalle_prompt("female", female_dalle_desc))

    print("\n推播到 Line...")
    messages = build_line_messages(
        analysis, len(pinterest_pins), len(rss_items),
        male_unsplash, female_unsplash,
        male_ai, female_ai,
    )
    send_line(messages)

    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()