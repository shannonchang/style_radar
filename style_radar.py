"""
AI 穿搭靈感雷達 - 每週自動推播
來源 A：Pinterest CSV（手動匯出，放進 data/pinterest.csv）
來源 B：穿搭媒體 RSS（Hypebeast、Highsnobiety 等）
來源 C：YouTube Data API（Dappei / Plain-me / MBM 等台灣頻道）
圖片：Unsplash API（真實照）+ gpt-image-1（AI 生成）
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
YOUTUBE_API_KEY            = os.environ.get("YOUTUBE_API_KEY", "")
PINTEREST_APP_ID           = os.environ.get("PINTEREST_APP_ID", "")
PINTEREST_APP_SECRET       = os.environ.get("PINTEREST_APP_SECRET", "")
PINTEREST_ACCESS_TOKEN     = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_REFRESH_TOKEN    = os.environ.get("PINTEREST_REFRESH_TOKEN", "")
PAT_TOKEN                  = os.environ.get("PAT_TOKEN", "")          # Fine-grained PAT，用來寫回 Secrets
GITHUB_REPOSITORY          = os.environ.get("GITHUB_REPOSITORY", "")  # owner/repo

# YouTube 頻道名稱（用搜尋方式找 channelId，不需要手動維護 ID）
YOUTUBE_CHANNELS = [
    "Dappei 搭配",   # 台灣最大穿搭社群
    "Plain-me",      # 台灣選物品牌
    "MBM",           # 台灣男生穿搭
    "Kevin老師",     # 穿搭教學
    "Lo-Fi House",   # 生活風格
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

FASHION_RSS = [
    ("MEN'S NON-NO", "https://mensnonno.jp/blog/feed"),
("MEN's FOLIO", "https://mens-folio.com/feed"),
("GQ Taiwan", "https://www.gq.com.tw/feed"),
("Yakkun Fashion", "https://yakkun-fashion.jp/feed"),
("MEN'S NON-NO", "https://www.mensnonno.jp/feed/"),
    ("Yakkun Fashion", "https://yakkun-fashion.jp/feed/"),
    ("BEAUTY美人圈", "https://www.beauty321.com/feed"),
    ("MERY JP", "https://mery.jp/feed"),
    ("Shopping Design", "https://www.shoppingdesign.com.tw/rss"),
]

STYLE_PREFERENCE = """
核心風格：
- clean fit
- relaxed silhouette
- effortless style
- 亞洲男生比例優化
- 韓系 + 日系混合
- 都市機能簡約

配色偏好：
- 黑
- 灰
- 白
- 深藍
- 大地色
- 低彩度

喜歡單品：
- NB 復古鞋
- 寬鬆西裝褲
- 直筒卡其褲
- 短版外套
- clean sneakers
- 尼龍機能材質
- 襯衫疊穿
- 針織

輪廓偏好：
- 上寬下直
- 不貼身
- 有空氣感
- 鬆弛感
- 日系垂墜感

避免：
- 過度 logo
- 浮誇高街
- oversize 太極端
- 全身精品感
- 緊身褲
- 美式健身風
- 螢光色
- heavy streetwear

風格參考：
- 韓國街頭上班族
- 東京選物店店員
- plain-me
- niko and...
- muji casual
- auralee / graphpaper 氛圍
"""

TAIWAN_WEATHER_RULES = """
台灣穿搭優先考量：

氣候特性：
- 潮濕悶熱、長時間高濕度
- 夏季均溫 28-35°C
- 室內冷氣與室外溫差大（常差 10°C）
- 突發降雨頻繁
- 機車 / 捷運通勤為主

穿搭原則：
- 透氣優先，避免厚磅重疊
- 可層次但不厚重，冷氣房一件薄外套即可
- 適合流汗、快乾材質
- 可快速穿脫
- 長時間步行仍舒適

優先材質：
- 尼龍、薄棉、Airism 類型
- 輕薄針織、機能布料、快乾材質

避免：
- 厚重衛衣、羊毛大衣
- 過厚丹寧、多層工裝
- 高領堆疊、歐美冬季穿搭

鞋款考量：
- 適合下雨天或潮濕地面
- 長時間步行舒適
- NB 復古鞋優先
"""

WEATHER_STYLE_MAP = {
    "32C+":   {"top": ["oversized tee", "airy shirt"],
               "bottom": ["wide shorts", "light slacks"],
               "fabric": ["nylon", "airism", "dry-fit"]},
    "26-31C": {"top": ["short sleeve shirt", "thin tee"],
               "outer": ["light shirt jacket"]},
    "20-25C": {"top": ["knit polo", "long sleeve tee"],
               "outer": ["light coach jacket"]},
    "15-19C": {"outer": ["short jacket", "light wool jacket"]},
}

OUTFIT_RULES = """
穿搭需：
- 適合台灣氣候
- 真實可日常穿出門
- 避免過度用力
- 不要 runway 感
- 可直接在 UNIQLO / GU / plain-me / Net 購買類似款
"""

FALLBACK_QUERIES = {
    "male": [
        "japanese minimal menswear",
        "korean relaxed fit men",
        "asian street casual men",
        "urban clean fit men",
        "tokyo select shop style",
        "muji menswear style",
        "plain me style men",
        "nb 990 outfit men",
        "wide pants menswear asian",
        "city boy style japan"
    ],

    "female": [
        "korean minimal women outfit",
        "japanese casual women fashion",
        "clean girl asian fashion",
        "relaxed silhouette women",
        "tokyo cafe girl outfit",
        "muji casual women style",
        "low tone korean outfit",
        "grey white black women outfit",
        "soft minimal fashion women",
        "urban effortless women style"
    ]
}


# ──────────────────────────────────────────
# Pinterest Token 自動更新
# ──────────────────────────────────────────
def refresh_pinterest_token() -> str:
    """
    用 refresh_token 換新的 access_token。
    換成功後自動把新的兩個 token 更新回 GitHub Secrets，
    這樣下次 Actions 執行時仍然有效。
    回傳新的 access_token，失敗回傳空字串。
    """
    if not all([PINTEREST_APP_ID, PINTEREST_APP_SECRET, PINTEREST_REFRESH_TOKEN]):
        print("  ⚠️ Pinterest refresh 所需變數不完整，跳過")
        return ""

    try:
        resp = requests.post(
            "https://api.pinterest.com/v5/oauth/token",
            auth=(PINTEREST_APP_ID, PINTEREST_APP_SECRET),
            data={
                "grant_type":    "refresh_token",
                "refresh_token": PINTEREST_REFRESH_TOKEN,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        new_access  = data.get("access_token", "")
        new_refresh = data.get("refresh_token", PINTEREST_REFRESH_TOKEN)

        print("  ✅ Pinterest token refresh 成功")

        # 把新 token 寫回 GitHub Secrets
        _update_github_secret("PINTEREST_ACCESS_TOKEN", new_access)
        _update_github_secret("PINTEREST_REFRESH_TOKEN", new_refresh)

        return new_access

    except Exception as e:
        print(f"  ❌ Pinterest token refresh 失敗：{e}")
        return ""


def _update_github_secret(secret_name: str, secret_value: str):
    """透過 Fine-grained PAT 加密寫入 GitHub Secrets"""
    if not PAT_TOKEN or not GITHUB_REPOSITORY:
        print(f"  ⚠️ 無法更新 {secret_name}：PAT_TOKEN 或 GITHUB_REPOSITORY 未設定")
        return

    try:
        # Step 1：取得 repo public key（加密用）
        key_resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/secrets/public-key",
            headers={
                "Authorization": f"Bearer {PAT_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        key_resp.raise_for_status()
        key_data   = key_resp.json()
        public_key = key_data["key"]
        key_id     = key_data["key_id"]

        # Step 2：用 libsodium 加密 secret value
        from base64 import b64decode, b64encode
        from nacl import public as nacl_public

        pk  = nacl_public.PublicKey(b64decode(public_key))
        box = nacl_public.SealedBox(pk)
        enc = b64encode(box.encrypt(secret_value.encode("utf-8"))).decode("utf-8")

        # Step 3：PUT 加密寫入 Secret
        put_resp = requests.put(
            f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/secrets/{secret_name}",
            headers={
                "Authorization": f"Bearer {PAT_TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"encrypted_value": enc, "key_id": key_id},
            timeout=10,
        )
        put_resp.raise_for_status()
        print(f"  ✅ GitHub Secret {secret_name} 已更新")

    except ImportError:
        print("  ⚠️ 缺少 PyNaCl，請執行：pip install PyNaCl")
    except Exception as e:
        print(f"  ❌ 更新 GitHub Secret {secret_name} 失敗：{e}")


# ──────────────────────────────────────────
# 來源 A：Pinterest API（fallback：CSV）
# ──────────────────────────────────────────
def fetch_pinterest_api(max_pins: int = 30, access_token_override: str = "") -> list[dict]:
    """
    用 Pinterest API v5 抓自己的 pins
    先取所有 boards，再逐一抓各 board 的最新 pins
    """
    token = access_token_override or PINTEREST_ACCESS_TOKEN
    if not token:
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Step 1：取所有 boards
    try:
        resp = requests.get(
            "https://api.pinterest.com/v5/boards",
            headers=headers,
            params={"page_size": 50},
            timeout=15,
        )
        resp.raise_for_status()
        boards = resp.json().get("items", [])
        print(f"  取得 {len(boards)} 個 boards")
    except Exception as e:
        print(f"  ❌ Pinterest boards 失敗：{e}")
        return []

    # Step 2：逐 board 抓 pins
    all_pins = []
    per_board = max(3, max_pins // max(len(boards), 1))

    for board in boards:
        board_id   = board["id"]
        board_name = board["name"]
        try:
            resp = requests.get(
                f"https://api.pinterest.com/v5/boards/{board_id}/pins",
                headers=headers,
                params={
                    "page_size": per_board,
                    "fields": "id,title,description,note,board_id",
                },
                timeout=15,
            )
            resp.raise_for_status()
            pins = resp.json().get("items", [])
            for pin in pins:
                all_pins.append({
                    "source": "Pinterest",
                    "title":  (pin.get("title") or "").strip(),
                    "note":   (pin.get("description") or pin.get("note") or "").strip(),
                    "board":  board_name,
                })
            if len(all_pins) >= max_pins:
                break
        except Exception as e:
            print(f"  ❌ board {board_name} 失敗：{e}")
            continue

    print(f"  ✅ Pinterest API：{len(all_pins)} 筆 pins")
    return all_pins[:max_pins]


def load_pinterest_csv() -> list[dict]:
    """CSV fallback：Pinterest API 不可用時使用"""
    csv_path = Path("data/pinterest.csv")
    if not csv_path.exists():
        return []

    mtime = datetime.fromtimestamp(csv_path.stat().st_mtime, tz=timezone.utc)
    age_days = (datetime.now(tz=timezone.utc) - mtime).days
    if age_days > 8:
        print(f"  ⚠️ Pinterest CSV 已 {age_days} 天未更新")

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
    print(f"  📁 Pinterest CSV fallback：{len(pins)} 筆")
    return pins


def collect_pinterest() -> list[dict]:
    """
    優先用 API，access_token 過期時自動 refresh。
    全部失敗才 fallback 到 CSV。
    """
    token = PINTEREST_ACCESS_TOKEN

    if PINTEREST_REFRESH_TOKEN:
        # 每次執行都先 refresh，確保 token 是新的
        print("  自動 refresh Pinterest token...")
        new_token = refresh_pinterest_token()
        if new_token:
            token = new_token

    if token:
        print("  使用 Pinterest API")
        pins = fetch_pinterest_api(access_token_override=token)
        if pins:
            return pins
        print("  ⚠️ API 失敗，嘗試 CSV fallback...")
    else:
        print("  Pinterest token 不可用，使用 CSV")

    return load_pinterest_csv()


# ──────────────────────────────────────────
# 來源 C：YouTube Data API
# ──────────────────────────────────────────
def _get_channel_id(channel_name: str) -> str | None:
    """用頻道名稱搜尋 channelId（消耗 ~100 quota）"""
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": channel_name,
                "type": "channel",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]
    except Exception as e:
        print(f"  ❌ 搜尋頻道 {channel_name} 失敗：{e}")
    return None


def _get_uploads_playlist_id(channel_id: str) -> str | None:
    """取得頻道的 uploads playlist ID（消耗 ~1 quota）"""
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "contentDetails",
                "id": channel_id,
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items:
            return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except Exception as e:
        print(f"  ❌ 取得 playlist 失敗：{e}")
    return None


def fetch_youtube_channel(channel_name: str, max_videos: int = 3) -> list[dict]:
    """
    抓取單一 YouTube 頻道的最新影片
    每次呼叫約消耗 ~103 quota（search 100 + channels 1 + playlistItems 2）
    6 個頻道每週一次 ≈ 618 quota，遠低於每日 10,000 上限
    """
    if not YOUTUBE_API_KEY:
        return []

    channel_id = _get_channel_id(channel_name)
    if not channel_id:
        return []

    playlist_id = _get_uploads_playlist_id(channel_id)
    if not playlist_id:
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params={
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": max_videos,
                "key": YOUTUBE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])

        results = []
        for item in items:
            sn = item["snippet"]
            title = sn.get("title", "").strip()
            desc  = sn.get("description", "").strip()[:300]
            video_id = sn.get("resourceId", {}).get("videoId", "")
            results.append({
                "source":   f"YouTube/{channel_name}",
                "title":    title,
                "desc":     desc,
                "video_id": video_id,
            })

        print(f"  ✅ YouTube/{channel_name}：{len(results)} 支影片")
        return results

    except Exception as e:
        print(f"  ❌ YouTube/{channel_name} playlist 失敗：{e}")
        return []


def collect_youtube_videos() -> list[dict]:
    """抓取所有設定頻道的最新影片"""
    if not YOUTUBE_API_KEY:
        print("  ⚠️ YOUTUBE_API_KEY 未設定，跳過來源 C")
        return []

    all_videos = []
    for channel_name in YOUTUBE_CHANNELS:
        all_videos.extend(fetch_youtube_channel(channel_name))
    return all_videos


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
def _call_gpt_image(dalle_prompt: str) -> dict:
    """呼叫 gpt-image-1 API，回傳 response json"""
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-image-1",
            "prompt": dalle_prompt,
            "n": 1,
            "size": "1024x1024",
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def generate_dalle_image(dalle_prompt: str) -> str | None:
    try:
        import base64, tempfile, os as _os
        # 最多 retry 一次
        try:
            data = _call_gpt_image(dalle_prompt)
        except Exception as retry_e:
            print(f"  ⚠️ 第一次失敗（{retry_e}），retry 中...")
            data = _call_gpt_image(dalle_prompt)

        # gpt-image-1 回傳 base64 字串
        b64 = data["data"][0].get("b64_json")
        if not b64:
            # 部分版本仍回傳 url
            url = data["data"][0].get("url")
            if url:
                print(f"  ✅ gpt-image-1 生成成功（url）")
                return url
            print(f"  ❌ gpt-image-1 回傳格式異常")
            return None

        # 將 base64 寫入暫存 PNG，上傳到 imgur（免費匿名）
        img_bytes = base64.b64decode(b64)
        imgur_resp = requests.post(
            "https://api.imgur.com/3/image",
            headers={"Authorization": "Client-ID 546c25a59c58ad7"},
            files={"image": ("outfit.png", img_bytes, "image/png")},
            timeout=30,
        )
        imgur_resp.raise_for_status()
        url = imgur_resp.json()["data"]["link"]
        print(f"  ✅ gpt-image-1 生成成功，上傳至 Imgur")
        return url

    except Exception as e:
        print(f"  ❌ gpt-image-1 失敗：{e}")
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
def build_prompt(pinterest_pins: list[dict], rss_items: list[dict], youtube_videos: list[dict] = None) -> str:
    sections = []

    if pinterest_pins:
        lines = [f"- [{p['board']}] {p['title']} {p['note']}".strip()
                 for p in pinterest_pins]
        sections.append(f"【Pinterest 收藏 {len(pinterest_pins)} 張】\n" + "\n".join(lines))

    if rss_items:
        lines = [f"- [{i['source']}] {i['title']}" for i in rss_items]
        sections.append(f"【穿搭媒體本週文章 {len(rss_items)} 篇】\n" + "\n".join(lines))

    if youtube_videos:
        lines = []
        for v in youtube_videos:
            desc_preview = v["desc"][:120].replace("\n", " ") if v["desc"] else ""
            line = f"- [{v['source']}] {v['title']}"
            if desc_preview:
                line += f"\n  └ {desc_preview}"
            lines.append(line)
        sections.append(f"【YouTube 台灣穿搭頻道本週影片 {len(youtube_videos)} 支】\n" + "\n".join(lines))

    combined = "\n\n".join(sections) if sections else "（本週沒有任何資料）"

    return f"""你是台灣在地穿搭顧問，同時熟悉男生和女生的穿搭趨勢。

【風格偏好】
{STYLE_PREFERENCE}

【台灣氣候穿搭規則】（所有建議必須符合）
{TAIWAN_WEATHER_RULES}

【穿搭輸出規則】
{OUTFIT_RULES}

以下是這週的穿搭資料：
{combined}

請用繁體中文回答，格式如下：

🎯 本週風格信號
（3 個本週最明顯的趨勢關鍵字，男女通用）

👨 男生穿搭建議
（符合台灣氣候的具體穿搭，說明材質和版型，可直接出門穿的程度）

👩 女生穿搭建議
（符合台灣氣候的具體穿搭，說明材質和版型，可直接出門穿的程度）

🌡️ 本週適合氣溫區間
（根據建議列出適合的溫度，例如：26-31°C）

📰 值得關注
（從媒體文章挑 1 篇最值得看的，一句話說原因）

📐 本週色系傾向
（一句話）

---
最後在回答最末尾，另起一行加上以下四行（供圖片生成使用，不要給用戶看）：
MALE_QUERY: [3-5個英文關鍵字，給 Unsplash 搜尋真實穿搭照]
FEMALE_QUERY: [3-5個英文關鍵字，給 Unsplash 搜尋真實穿搭照]
MALE_DALLE: [10-15個英文單字，描述男生本週穿搭的具體單品和顏色，給 gpt-image-1 生成圖用]
FEMALE_DALLE: [10-15個英文單字，描述女生本週穿搭的具體單品和顏色，給 gpt-image-1 生成圖用]

語氣像朋友，不要像 AI 報告，220 字以內。"""


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


def analyze_with_claude(pinterest_pins: list[dict], rss_items: list[dict], youtube_videos: list[dict] = None):
    if not pinterest_pins and not rss_items and not youtube_videos:
        return "本週三個來源都沒有資料，請確認 Pinterest CSV 是否放入 data/ 資料夾、YOUTUBE_API_KEY 是否設定。", "", "", "", ""

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
            "messages": [{"role": "user", "content": build_prompt(pinterest_pins, rss_items, youtube_videos)}],
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
    youtube_count: int,
    male_unsplash: str | None,
    female_unsplash: str | None,
    male_dalle: str | None,
    female_dalle: str | None,
) -> list[dict]:
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%m/%d")
    header = (
        f"👗 穿搭雷達週報 {today}\n"
        f"📌 Pinterest {pinterest_count} 張｜媒體 {rss_count} 篇｜YouTube {youtube_count} 支\n"
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
            add_image(male_dalle, "🎨 AI 風格示意圖（gpt-image-1）")

    # 女生圖片
    if female_unsplash or female_dalle:
        messages.append({"type": "text", "text": "── 👩 女生參考圖 ──"})
        if female_unsplash:
            add_image(female_unsplash, "📷 真實穿搭參考（Unsplash）")
        if female_dalle:
            add_image(female_dalle, "🎨 AI 風格示意圖（gpt-image-1）")

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

    print("[來源 A] Pinterest")
    pinterest_pins = collect_pinterest()

    print("\n[來源 B] 穿搭媒體 RSS")
    rss_items = collect_fashion_rss()

    print("\n[來源 C] YouTube 台灣穿搭頻道")
    youtube_videos = collect_youtube_videos()

    print(f"\n合計：Pinterest {len(pinterest_pins)} 筆｜媒體 {len(rss_items)} 篇｜YouTube {len(youtube_videos)} 支")

    print("\nClaude 分析中...")
    analysis, male_query, female_query, male_dalle_desc, female_dalle_desc = \
        analyze_with_claude(pinterest_pins, rss_items, youtube_videos)
    print(f"\n{analysis}")
    print(f"\nUnsplash 關鍵字 → 男：{male_query}｜女：{female_query}")
    print(f"DALL-E 描述 → 男：{male_dalle_desc}｜女：{female_dalle_desc}")

   # print("\n[圖片] Unsplash 搜尋...")
   # male_unsplash   = fetch_unsplash_image(male_query,   gender="male")
   # female_unsplash = fetch_unsplash_image(female_query, gender="female")

    #print("\n[圖片] gpt-image-1 生成...")
    #male_ai   = generate_dalle_image(build_dalle_prompt("male",   male_dalle_desc))
    #female_ai = generate_dalle_image(build_dalle_prompt("female", female_dalle_desc))

    print("\n推播到 Line...")
    messages = build_line_messages(
        analysis,
        len(pinterest_pins),
        len(rss_items),
        len(youtube_videos),
        '', '', '', '',
        #male_unsplash, female_unsplash,
        #male_ai, female_ai,
    )
    send_line(messages)

    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()