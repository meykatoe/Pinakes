# Pinakes

自架媒體整理工具。把下載好的電影、影集丟進資料夾，Pinakes 會用 TMDB（與選用的 AI）辨識片名，依命名樣板整理進媒體庫，並產生可直接播放的海報牆。

## 功能

- 自動辨識：解析檔名中的片名、年份、季集、解析度，到 TMDB 比對；不確定時可讓 AI 協助判斷
- 安全整理：預設使用硬連結，不動原檔、可繼續做種；也支援移動、複製、軟連結，每個動作都能還原
- 自動監控：偵測下載完成（檔案大小穩定）後自動處理，完成後可寄 Email 摘要，或推送到 Telegram、Discord
- 雲端同步：定時掃描你用 rclone 掛載的資料夾（如 PikPak），把新檔複製到待整理目錄並自動整理，雲端原檔保留
- 人工確認：無法確定的項目列為待確認，可從候選或手動搜尋 TMDB 指定，也能修正電影或影集類型；同一部影集的多個檔案可勾選後一次指定，各集保留自己的季集
- 媒體資訊檔：可選擇輸出 NFO 與海報圖，供 Jellyfin、Emby、Kodi 讀取，已存在的檔案不覆蓋，還原時一併移除
- 海報牆：自動下載海報、背景圖、簡介、演員與預告片，依分類分列，可一鍵移出媒體庫
- 內建播放：瀏覽器可播放的格式直接串流，其他格式用 ffmpeg 即時轉碼，支援跳轉、續播與外掛字幕（srt、ass、vtt，自動轉碼與編碼偵測）
- 外部播放器：一鍵送到 PotPlayer、VLC、IINA，或下載 m3u 清單
- 自訂規則：命名樣板、正則辨識規則、自訂分類
- 登入保護：可設定密碼，深淺色主題，手機版面

## 快速開始（Docker）

映像檔發佈在 GitHub Container Registry：`ghcr.io/meykatoe/pinakes`，支援 `linux/amd64` 與 `linux/arm64`。

先準備資料夾。若要使用硬連結，下載目錄與媒體庫必須在同一個掛載點底下，例如：

    /mnt/data/downloads   下載目錄
    /mnt/data/media       媒體庫

### 方式一：docker run

    mkdir -p config
    docker run -d --name pinakes --restart unless-stopped \
      --user 1000:1000 -p 8000:8000 -e TZ=Asia/Taipei \
      -v "$PWD/config:/config" -v /mnt/data:/data \
      ghcr.io/meykatoe/pinakes:latest

### 方式二：docker compose

    mkdir pinakes && cd pinakes && mkdir config
    curl -O https://raw.githubusercontent.com/meykatoe/Pinakes/main/docker-compose.yml
    DATA_PATH=/mnt/data docker compose up -d

`DATA_PATH` 是你的資料根目錄。也可以直接修改 `docker-compose.yml` 裡的 `/path/to/data`，之後就只要 `docker compose up -d`。

### 開始使用

開啟 `http://伺服器IP:8000`，依引導填入 TMDB 金鑰，並選擇 `/data/downloads` 與 `/data/media`。

TMDB 金鑰可到 [TMDB 帳號設定](https://www.themoviedb.org/settings/api) 免費申請。

### 更新與版本

    # docker compose
    docker compose pull && docker compose up -d
    # docker run
    docker pull ghcr.io/meykatoe/pinakes:latest
    docker rm -f pinakes   # 再重新執行上面的 docker run 指令

設定與資料庫都在 `config` 資料夾，更新不會遺失。想固定版本可把 `latest` 改成指定版本，例如 `1.0.0`。

### 注意事項

- 容器以 UID/GID 1000 執行，可用 `PUID`、`PGID`（compose）或 `--user`（docker run）調整，確保對 `config` 與媒體目錄有讀寫權限。
- Windows 的 Docker Desktop 無法對掛載的 Windows 資料夾建立硬連結，請把整理模式改成「複製」，或改用下方的 Windows 安裝程式。
- 想自行建置映像檔：在專案根目錄執行 `docker compose up -d --build`（需先取消 `docker-compose.yml` 中 `build: .` 的註解）。

## Windows 安裝程式

到 [Releases](https://github.com/meykatoe/Pinakes/releases) 下載 `Pinakes-Setup.exe`，安裝後從開始選單啟動，右下角系統匣會出現圖示。已內附 Python 與 ffmpeg，不需另外安裝，資料存放在 `%APPDATA%\pinakes`。

## 手動安裝

需要 Python 3.14、[uv](https://docs.astral.sh/uv/)、Node.js 22 以上，內建播放需要 ffmpeg。

    cd frontend && npm ci && npm run build
    cd ../backend && uv sync --no-dev
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

後端會一併提供 `frontend/dist` 的前端頁面，開啟 `http://localhost:8000` 即可使用。

## 設定

大部分設定都在網頁的「設定」頁完成。下列環境變數用於部署：

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `PINAKES_DATA_DIR` | `data` | 資料庫、金鑰、海報快取的位置 |
| `PINAKES_STATIC_DIR` | `../frontend/dist` | 前端建置檔位置 |
| `PINAKES_WATCH_LOOP` | `true` | 是否啟動背景監控與轉碼清理 |
| `PINAKES_CORS_ORIGINS` | `["http://localhost:5173"]` | 開發時允許的前端來源 |

API 金鑰與 SMTP 密碼會以 `PINAKES_DATA_DIR/secret.key` 加密儲存，備份時請一併保留這個檔案。

## 反向代理

經由 Nginx 等反向代理時：

- 在「設定 > 播放」填入對外網址，外部播放器才拿得到正確的串流網址
- 手動掃描大量檔案可能需要較久，建議調高逾時，例如 `proxy_read_timeout 600s;`
- 若使用 HTTPS，登入 Cookie 會自動加上 Secure

## 通知

在「設定 > 通知」可同時啟用多種管道，全部在網頁填寫，不需改程式：

- Email：填入 SMTP 資訊
- Telegram：向 @BotFather 建立機器人取得金鑰，並填入自己的聊天室 ID
- Discord：在頻道的「整合 > Webhook」建立並貼上網址

## 雲端同步（rclone）

Pinakes 不負責連接雲端，請先自行用 rclone 掛載，例如：

    rclone mount pikpak:/ /mnt/pikpak --vfs-cache-mode full --rc

接著到「設定 > 媒體庫 > 雲端同步」選擇掛載後的來源資料夾與檢查間隔（預設 30 分鐘）。

- 只會複製影片與字幕，雲端原檔不會被刪除或移動
- 已同步的檔案會記錄在資料庫，之後即使整理時移走也不會重複下載
- 掛載有目錄快取，雲端新增的檔案可能延遲出現。掛載時加上 `--rc`，並在設定填入遠端控制網址（預設 `http://127.0.0.1:5572`），每次同步前會先刷新
- 「同步後自動辨識與整理」關閉時只複製到待整理目錄；若同時開啟「自動監控」，監控仍會處理這些檔案
- Docker 部署時，掛載目錄需讓容器讀取到，例如在 `docker-compose.yml` 加上 `/mnt/pikpak:/mnt/pikpak:ro,rslave`（已附註解範例）

### 雲端整理（選用）

預設雲端原檔會保留。若希望雲端的檔案也跟本地一樣整理好，可在「設定 > 媒體庫 > 雲端整理」啟用：本地整理成功後，會透過 rclone 遠端控制在雲端把原檔**搬移並改名**到雲端媒體庫，結構與本地媒體庫相同。

需要的設定：

- rclone 掛載時加上 `--rc`，並在上方填入遠端控制網址（若有 `--rc-user`、`--rc-pass` 也一併填入）
- 雲端來源：對應掛載來源資料夾的 rclone 路徑，例如 `pikpak:/downloads`
- 雲端媒體庫：整理後存放位置，例如 `pikpak:/Media`

注意事項：

- 搬移是雲端內部的重新命名，不經過本機下載。來源與媒體庫請使用同一個遠端；跨遠端或不支援伺服器端搬移的雲端，rclone 會改成下載再上傳，速度慢且耗頻寬
- 雲端媒體庫不可位於雲端來源之內，否則搬過去的檔案會被當成新檔重新同步
- 原位置不再保留原檔，在 Pinakes 按「還原」只還原本地，不會把雲端檔案搬回去。建議先用少量檔案測試
- 雲端目標已存在同名檔案時不會覆蓋，該檔案會記為失敗並通知一次，最多重試 5 次
- 字幕等附屬檔會跟著影片一起搬移

## 忘記密碼

在伺服器執行下列指令清除密碼，再到設定頁重新設定：

    # Docker
    docker compose exec pinakes python -m app.cli reset-password
    # 手動安裝
    cd backend && uv run python -m app.cli reset-password

## 外部播放器

串流網址帶有權杖，不需登入即可播放，適合在其他裝置的播放器開啟；若網址外流，可在設定頁重新產生權杖。

- PotPlayer：安裝後即註冊 `potplayer://`
- VLC：需另外安裝協定註冊工具才能使用 `vlc://`
- 手機或其他播放器：使用「下載 m3u 清單」或「複製連結」

## 開發

    # 後端（埠 8000）
    cd backend && uv run uvicorn app.main:app --reload
    # 前端（埠 5173，自動轉發 /api）
    cd frontend && npm run dev

測試：

    cd backend && uv run pytest
    cd frontend && npx vue-tsc -b && npm test

### 版本號

版本號以 `backend/pyproject.toml` 為準，用腳本同步其餘檔案（後端 `__init__.py`、`uv.lock`、前端 `package.json` 與鎖定檔）：

    python scripts/version.py show
    python scripts/version.py set 1.2.0
    python scripts/version.py check

後端測試會檢查版本是否一致，打 `v*` 標籤發佈時也會檢查標籤與版本號相同。

### 分支與發佈

- `dev`：開發與測試。推送到 `dev` 或對 `dev`、`main` 開 PR 時，會自動跑後端 ruff 與 pytest、前端建置，以及 Docker 映像建置驗證，不會發佈。
- `main`：穩定版。確認 `dev` 沒問題後手動合併到 `main`，會先重跑測試，通過才把映像推到 GHCR（`latest` 與 `sha-<短雜湊>`）。
- 打 `v*` 標籤時另外發佈版本映像（例如 `1.2.0`、`1.2`）。
- 依賴更新由 dependabot 每週檢查，PR 一律開到 `dev`，通過 CI 後再隨 `dev` 合併。

## 名稱由來

Pinakes（希臘語 Πίνακες，意為「板、目錄」）是 Pinax 的複數形。

西元前三世紀，詩人兼學者卡利馬科斯（Callimachus）為亞歷山大圖書館編寫館藏目錄，書名即為 Pinakes。
它依主題與作者分類，並附上作品資訊，被視為史上最早的圖書分類目錄。

這個名字對應本專案的兩個核心：

- 整理分類：如同 Pinakes 為雜亂的館藏建立秩序。
- 圖像呈現：Pinax 也指畫板，對應海報牆。

---

This product uses the TMDB API but is not endorsed or certified by TMDB.
