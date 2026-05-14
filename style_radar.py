"""
AI 穿搭靈感雷達 - 每週自動推播
資料來源：Pinterest API v5
分析：Claude API
推播：Telegram Bot
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone


# ──────────────────────────────────────────
# 設定區（全部從環境變數讀取，不要硬寫在這裡）
# ──────────────────────────────────────────
PINTEREST_TOKEN = os.environ["PINTEREST_ACCESS_TOKEN"]
CLAUDE_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# 你想監控的 Pinterest board ID（見下方說明如何取得）
BOARD_IDS = os.environ.get("PINTEREST_BOARD_IDS", "").split(",")


# ──────────────────────────────────────────
# Step 1：抓本週新 Pins
# ──────────────────────────────────────────
def fetch_recent_pins(board_id: str, days: int = 7) -> list[dict]:
    """抓指定 board 最近 N 天的 pins"""
    url = f"https://api.pinterest.com/v5/boards/{board_id}/pins"
    headers = {"Authorization": f"Bearer {PINTEREST_TOKEN}"}
    params = {
        "page_size": 25,
        "fields": "id,title,description,media,link,created_at"
    }

    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    pins = resp.json().get("items", [])

    # 過濾本週內的
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = []
    for pin in pins:
        created = pin.get("created_at", "")
        if created:
            pin_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if pin_time >= cutoff:
                recent.append(pin)

    return recent


def collect_all_pins() -> list[dict]:
    all_pins = []
    for board_id in BOARD_IDS:
        board_id = board_id.strip()
        if not board_id:
            continue
        try:
            pins = fetch_recent_pins(board_id)
            all_pins.extend(pins)
            print(f"Board {board_id}：抓到 {len(pins)} 張")
        except Exception as e:
            print(f"Board {board_id} 失敗：{e}")
    return all_pins


# ──────────────────────────────────────────
# Step 2：用 Claude 分析風格趨勢
# ──────────────────────────────────────────
def build_pin_summary(pins: list[dict]) -> str:
    """把 pins 資訊整理成文字給 Claude 分析"""
    lines = []
    for i, pin in enumerate(pins, 1):
        title = pin.get("title") or ""
        desc  = pin.get("description") or ""
        lines.append(f"{i}. {title} {desc}".strip())
    return "\n".join(lines) if lines else "（本週沒有新收藏）"


def analyze_with_claude(pins: list[dict]) -> str:
    """呼叫 Claude API 分析本週收藏趨勢"""
    if not pins:
        return "本週沒有新的穿搭收藏，下週繼續 pin 吧！"

    summary = build_pin_summary(pins)

    prompt = f"""你是亞洲男生穿搭顧問。

以下是這週新收藏的穿搭（共 {len(pins)} 張）：
{summary}

請分析並用繁體中文回答，格式如下：

🎯 本週風格信號
（3 個關鍵字，例如：鬆弛感 / 灰白色系 / NB 復古）

📐 色系傾向
（一句話描述）

💡 下週可以嘗試
（一個具體穿搭方向，越實際越好）

語氣像朋友，不要像 AI 報告，100 字以內。"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


# ──────────────────────────────────────────
# Step 3：推播到 Telegram
# ──────────────────────────────────────────
def send_telegram(message: str):
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%m/%d")
    full_message = f"👗 穿搭雷達週報 {today}\n\n{message}"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": full_message,
        "parse_mode": "HTML",
    }, timeout=15)
    resp.raise_for_status()
    print("Telegram 推播成功")


# ──────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────
def main():
    print("=== 穿搭雷達啟動 ===")

    print("抓取本週 Pins...")
    pins = collect_all_pins()
    print(f"總共 {len(pins)} 張新收藏")

    print("Claude 分析中...")
    analysis = analyze_with_claude(pins)
    print(f"分析結果：\n{analysis}")

    print("推播到 Telegram...")
    send_telegram(analysis)

    print("=== 完成 ===")


if __name__ == "__main__":
    main()
