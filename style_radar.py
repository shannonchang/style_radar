"""
AI 穿搭靈感雷達 - 每週自動推播
來源 A：Pinterest CSV（手動匯出，放進 data/pinterest.csv）
來源 B：Reddit 公開 JSON（全自動，不需要 API key）
分析：Claude API
推播：Line Messaging API
"""

import os
import csv
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ──────────────────────────────────────────
# 設定區
# ──────────────────────────────────────────
CLAUDE_API_KEY     = os.environ["ANTHROPIC_API_KEY"]
LINE_CHANNEL_TOKEN = os.environ["LINE_CHANNEL_TOKEN"]
LINE_USER_ID       = os.environ["LINE_USER_ID"]

REDDIT_HEADERS = {"User-Agent": "zn-style-radar/1.0 (by ZN Studio)"}

SUBREDDITS = [
    "malefashionadvice",
    "japanesestreetwear",
    "streetwear",
    "frugalmalefashion",
    "Sneakers",
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
        print("Pinterest CSV 不存在，跳過")
        return []

    pins = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pins.append({
                "source": "Pinterest",
                "title": row.get("Title", "").strip(),
                "note": row.get("Note", "").strip(),
                "board": row.get("Board Name", "").strip(),
                "url": row.get("URL", "").strip(),
            })

    print(f"Pinterest CSV：讀到 {len(pins)} 筆")
    return pins


# ──────────────────────────────────────────
# 來源 B：Reddit 公開 JSON
# ──────────────────────────────────────────
def fetch_reddit_top(subreddit: str, limit: int = 8) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=week&limit={limit}"
    try:
        resp = requests.get(url, headers=REDDIT_HEADERS, timeout=15)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]
        return [{
            "source": f"r/{subreddit}",
            "title": p["data"].get("title", ""),
            "body": p["data"].get("selftext", "")[:300],
            "score": p["data"].get("score", 0),
            "permalink": f"https://reddit.com{p['data'].get('permalink', '')}",
        } for p in posts]
    except Exception as e:
        print(f"Reddit r/{subreddit} 失敗：{e}")
        return []


def collect_reddit_posts() -> list[dict]:
    all_posts = []
    for sub in SUBREDDITS:
        posts = fetch_reddit_top(sub)
        all_posts.extend(posts)
        print(f"Reddit r/{sub}：抓到 {len(posts)} 篇")
    return all_posts


# ──────────────────────────────────────────
# Claude 分析
# ──────────────────────────────────────────
def build_prompt(pinterest_pins: list[dict], reddit_posts: list[dict]) -> str:
    sections = []

    if pinterest_pins:
        lines = [f"- [{p['board']}] {p['title']} {p['note']}".strip()
                 for p in pinterest_pins]
        sections.append(f"【Pinterest 收藏（{len(pinterest_pins)} 張）】\n" + "\n".join(lines))

    if reddit_posts:
        lines = [f"- [{p['source']}] {p['title']} (score: {p['score']})"
                 for p in reddit_posts]
        sections.append(f"【Reddit 本週熱門（{len(reddit_posts)} 篇）】\n" + "\n".join(lines))

    combined = "\n\n".join(sections) if sections else "（本週沒有任何資料）"

    return f"""你是亞洲男生穿搭顧問。

我的風格偏好：
{STYLE_PREFERENCE}

以下是這週的穿搭資料：
{combined}

請根據我的風格偏好，用繁體中文回答，格式如下：

🎯 本週風格信號
（從收藏和熱門貼文中，找出 3 個符合我偏好的關鍵字）

📰 Reddit 值得關注
（挑 1～2 篇最值得看的，說明原因，附上標題）

📐 色系傾向
（一句話描述本週整體色調）

💡 下週可以嘗試
（一個具體穿搭方向，越實際越好）

語氣像朋友，不要像 AI 報告，150 字以內。"""


def analyze_with_claude(pinterest_pins: list[dict], reddit_posts: list[dict]) -> str:
    if not pinterest_pins and not reddit_posts:
        return "本週沒有收到任何資料，記得把 Pinterest CSV 放進 data/ 資料夾！"

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
            "messages": [{"role": "user", "content": build_prompt(pinterest_pins, reddit_posts)}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


# ──────────────────────────────────────────
# Line 推播
# ──────────────────────────────────────────
def send_line(message: str, pinterest_count: int, reddit_count: int):
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%m/%d")
    full_message = (
        f"👗 穿搭雷達週報 {today}\n"
        f"📌 Pinterest {pinterest_count} 張｜Reddit {reddit_count} 篇\n"
        f"{'─' * 20}\n\n"
        f"{message}"
    )

    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": full_message}],
        },
        timeout=15,
    )
    resp.raise_for_status()
    print("Line 推播成功")


# ──────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────
def main():
    print("=== 穿搭雷達啟動 ===")

    print("\n[來源 A] 讀取 Pinterest CSV...")
    pinterest_pins = load_pinterest_csv()

    print("\n[來源 B] 抓取 Reddit 本週熱門...")
    reddit_posts = collect_reddit_posts()

    print(f"\n合計：Pinterest {len(pinterest_pins)} 筆 + Reddit {len(reddit_posts)} 篇")

    print("\nClaude 分析中...")
    analysis = analyze_with_claude(pinterest_pins, reddit_posts)
    print(f"\n分析結果：\n{analysis}")

    print("\n推播到 Line...")
    send_line(analysis, len(pinterest_pins), len(reddit_posts))

    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
