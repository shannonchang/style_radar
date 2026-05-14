# 🎯 AI 穿搭靈感雷達

每週自動分析你的 Pinterest 收藏，推播風格趨勢到 Telegram。

---

## 檔案結構

```
style-radar-bot/
├── style_radar.py                          # 主程式
└── .github/
    └── workflows/
        └── weekly_style_radar.yml          # 自動排程
```

---

## 設定步驟

### 1. Telegram Bot Token & Chat ID

1. Telegram 搜尋 `@BotFather` → `/newbot` → 取得 Token
2. 對你的 Bot 按 Start，開啟瀏覽器：
   ```
   https://api.telegram.org/bot【TOKEN】/getUpdates
   ```
3. 找 `"chat":{"id":` 後面的數字 = Chat ID

---

### 2. Pinterest Access Token & Board ID

**取得 Access Token：**
1. 前往 [Pinterest Developers](https://developers.pinterest.com/)
2. 建立 App → 申請 `boards:read` + `pins:read` 權限
3. 用 OAuth 取得 Access Token

**取得 Board ID：**
1. 開啟你的 Pinterest board 頁面
2. URL 格式：`https://pinterest.com/你的帳號/board名稱/`
3. 或呼叫 API：
   ```
   GET https://api.pinterest.com/v5/boards
   Authorization: Bearer 【你的Token】
   ```
4. 回傳 JSON 裡每個 board 有 `id` 欄位

多個 Board 用逗號分隔：`123456789,987654321`

---

### 3. GitHub Secrets 設定

在你的 repo → Settings → Secrets and variables → Actions → New repository secret

| Secret 名稱 | 值 |
|---|---|
| `PINTEREST_ACCESS_TOKEN` | Pinterest OAuth token |
| `ANTHROPIC_API_KEY` | Claude API key |
| `TELEGRAM_BOT_TOKEN` | BotFather 給的 token |
| `TELEGRAM_CHAT_ID` | 你的 chat id（數字） |
| `PINTEREST_BOARD_IDS` | board id，多個用逗號分隔 |

---

### 4. 測試執行

設定完後，到 GitHub repo → Actions → 穿搭靈感雷達 → Run workflow

---

## 執行頻率

預設每週日 21:00 台灣時間自動執行。

修改頻率請編輯 `.github/workflows/weekly_style_radar.yml` 的 cron 設定：

```yaml
# 常用設定
每週日 21:00  → '0 13 * * 0'
每週一 08:00  → '0 0 * * 1'
每天 21:00    → '0 13 * * *'
```

---

## Telegram 推播格式範例

```
👗 穿搭雷達週報 05/18

🎯 本週風格信號
鬆弛感 / 灰白色系 / NB 復古

📐 色系傾向
這週明顯偏灰階，黑白灰佔了大半，
整體很乾淨。

💡 下週可以嘗試
試試深灰寬褲配白T，
腰間不要有太多細節，讓比例說話。
```
