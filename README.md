# Pinakes

自架媒體整理工具，串接 TMDB 與 OpenAI，自動整理影音檔並產生海報牆。

## 名稱由來

Pinakes（希臘語 Πίνακες，意為「板、目錄」）是 Pinax 的複數形。

西元前三世紀，詩人兼學者卡利馬科斯（Callimachus）為亞歷山大圖書館編寫館藏目錄，書名即為 Pinakes。
它依主題與作者分類，並附上作品資訊，被視為史上最早的圖書分類目錄。

這個名字對應本專案的兩個核心：

- 整理分類：如同 Pinakes 為雜亂的館藏建立秩序。
- 圖像呈現：Pinax 也指畫板，對應海報牆。

## 啟動

後端：

    cd backend && uv run uvicorn app.main:app --reload

前端：

    cd frontend && npm run dev

後端環境變數前綴為 `PINAKES_`，例如 `PINAKES_DATA_DIR`。
