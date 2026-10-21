Pinakes Windows 版

使用方式
1. 解壓縮到固定位置，例如 D:\Pinakes。
2. 雙擊 python\pythonw.exe 並開啟 tray.py，或使用安裝程式建立的捷徑。
3. 右下角系統匣會出現 Pinakes 圖示，雙擊開啟網頁，右鍵可設定開機自動啟動或結束。
4. 除錯時可雙擊 start.bat，會顯示主控台輸出。

注意事項
- 內附 Python 與 ffmpeg，不需要另外安裝，也不需要網路。
- 要使用硬連結，下載目錄與媒體庫必須在同一個 NTFS 磁碟機，例如都在 D:。
- 外部播放器在其他裝置時，請在設定填入「串流網址前綴」，並允許 Windows 防火牆放行 8000 連接埠。
- 資料與記錄存放在 %APPDATA%\pinakes，備份時請連同 secret.key 一併保留。
- 有 NVIDIA 顯卡時會自動使用 NVENC 硬體加速。
