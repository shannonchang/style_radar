# 🎯 AI 穿搭靈感雷達

每週自動分析 Pinterest 收藏、穿搭媒體 RSS、YouTube 台灣穿搭頻道，透過 Claude AI 生成風格建議並推播到 Line。

---

## 架構

```
來源 A：Pinterest API（自動抓取 boards/pins）
來源 B：穿搭媒體 RSS（Hypebeast / GQ Taiwan 等）
來源 C：YouTube Data API（Dappei / Plain-me / MBM 等台灣頻道）
          ↓
    GitHub Actions 每週日 21:00 自動觸發
          ↓
    Claude API 分析（含台灣氣候規則 + 個人風格偏好）
          ↓
Unsplash 真實穿搭照 + gpt-image-1 AI 生成圖
          ↓
    Line Messaging API 推播
```

---

## 檔案結構

```
style_radar/
├── style_radar.py                 # 主程式
├── pinterest_oauth.py             # Pinterest 一次性授權腳本
├── data/
│   └── pinterest.csv              # Pinterest CSV fallback（可選）
└── .github/
    └── workflows/
        └── weekly_style_radar.yml # 自動排程
```

---

## 設定步驟

### 1. Pinterest OAuth 授權

> ⚠️ 請先在瀏覽器登入**你有 boards 的 Pinterest 主帳號**，再執行以下步驟。

1. 前往 [Pinterest Developers](https://developers.pinterest.com/) 建立 App
2. App 設定頁加入 Redirect URI：`http://localhost:8080/callback`
3. 申請權限：`pins:read`、`boards:read`、`user_accounts:read`
4. 填入 `pinterest_oauth.py` 的 App ID / App Secret，執行：
   ```bash
   python pinterest_oauth.py
   ```
5. 瀏覽器授權後，終端機印出 `PINTEREST_ACCESS_TOKEN` 和 `PINTEREST_REFRESH_TOKEN`

> Token 每 24 小時過期，程式會自動 refresh 並寫回 GitHub Secrets。

---

### 2. YouTube Data API

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 啟用 **YouTube Data API v3**
3. 建立憑證 → API 金鑰
4. 每週 5 個頻道各抓 3 支影片，約消耗 515 quota（每日上限 10,000）

---

### 3. Line Messaging API

1. 前往 [Line Developers](https://developers.line.biz/)
2. 建立 Messaging API channel
3. 取得 Channel Access Token
4. 取得你的 User ID（在 Line Official Account Manager 的 Basic Settings）

---

### 4. GitHub Secrets 設定

repo → Settings → Secrets and variables → Actions → New repository secret

| Secret | 說明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `LINE_CHANNEL_TOKEN` | Line Channel Access Token |
| `LINE_USER_ID` | Line User ID |
| `UNSPLASH_ACCESS_KEY` | Unsplash API key |
| `OPENAI_API_KEY` | gpt-image-1 生成圖用 |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key |
| `PINTEREST_APP_ID` | Pinterest App ID |
| `PINTEREST_APP_SECRET` | Pinterest App Secret |
| `PINTEREST_ACCESS_TOKEN` | OAuth 授權後取得 |
| `PINTEREST_REFRESH_TOKEN` | OAuth 授權後取得 |
| `PAT_TOKEN` | Fine-grained PAT，用來自動更新 Pinterest token |

**PAT_TOKEN 建立方式：**

GitHub 個人頭像 → Settings → Developer settings → Personal access tokens → Fine-grained tokens

| 欄位 | 值 |
|------|----|
| Repository access | 只選這個 repo |
| Permissions → Secrets | Read and Write |

---

### 5. 測試執行

設定完後：repo → Actions → 穿搭靈感雷達 → Run workflow

---

## 執行頻率

預設每週日 21:00 台灣時間自動執行。

```yaml
每週日 21:00  → '0 13 * * 0'
每週一 08:00  → '0 0 * * 1'
每天 21:00    → '0 13 * * *'
```

---

## Line 推播格式

```
👗 穿搭雷達週報 05/25
📌 Pinterest 28 張｜媒體 12 篇｜YouTube 15 支
────────────────────

🎯 本週風格信號
鬆弛感 / 灰白色系 / NB 復古

👨 男生穿搭建議
薄棉寬版短袖 + 直筒卡其褲 + NB 990，
適合台灣 28-32°C 悶熱天氣，快乾材質優先。

👩 女生穿搭建議
無袖亞麻上衣 + 寬版長褲，
輕薄透氣，室內外溫差大時加一件薄針織。

🌡️ 本週適合氣溫區間
26-32°C

📰 值得關注
Dappei：〈這個夏天必備的 5 件基本款〉
台灣在地選品角度，直接可買。

📐 本週色系傾向
灰白大地為主，低彩度整體感強。

── 👨 男生參考圖 ──
📷 真實穿搭參考（Unsplash）
🎨 AI 風格示意圖（gpt-image-1）

── 👩 女生參考圖 ──
📷 真實穿搭參考（Unsplash）
🎨 AI 風格示意圖（gpt-image-1）
```
