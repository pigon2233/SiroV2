# Wine 啟動實測（2026-10-19）

使用者只有 Linux，已明確要求嘗試 Wine。本輪安裝與啟動通過，CP-V03 整卡仍未完成。

- Wine 10.0；隔離 prefix `/home/jasonliao/.local/share/siro-cubism-wine`，未改既有 `~/.wine` 的 LTspice。
- 官方 Windows Cubism 5.2.03 安裝包，NSIS `/S /D=C:\Cubism`，installer exit 0。
- `CubismEditor5.exe` 啟動後產生 Java 主程序、Editor 主視窗與 Start 對話框。
- Editor log 確認 OpenGL 4.6 Core／Mesa 初始化；主視窗標示 Unregistered。
- 未購買、啟用 PRO／試用，也未聲稱 PSD 匯入、保存、匯出或 renderer 往返通過。

重開命令（無需重新安裝）：

```bash
cd /home/jasonliao/.local/share/siro-cubism-wine/drive_c/Cubism
WINEPREFIX=/home/jasonliao/.local/share/siro-cubism-wine wine CubismEditor5.exe
```

原始軟體／安裝包留本機，不加入 Git。`receipt.json` 記錄安裝包來源、大小及 SHA-256；`startup-excerpt.txt` 與 `window-titles.txt` 為真實啟動證據。

下一步在 Start 選擇 FREE，執行 TOOLCHAIN.md 的兩層工程往返流程。啟動成功不保證後續 mesh、atlas、授權檢查或匯出均相容。

[官方下載](https://www.live2d.com/en/cubism/download/editor/)／[官方平台需求](https://www.live2d.com/en/cubism/download/spec/)。Wine 是本機實驗路徑，官方頁面未列 Linux 支援。
