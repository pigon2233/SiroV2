# Body assets

不要把 Cubism Core、角色模型、貼圖或聲音直接提交到 Git。每組本機資產放在被忽略的子目錄，並建立 `asset-manifest.json`，至少記錄官方來源、授權名稱／網址、接受條款的人與時間，以及每個檔案的 SHA-256。

manifest 格式由 `siro.adapters.body.assets.BodyAssetManifest` 驗證。範例：

```json
{
  "schema_version": 1,
  "asset_id": "live2d.owner-model",
  "source_url": "https://official.example/download",
  "license_name": "Applicable asset license",
  "license_url": "https://official.example/license",
  "accepted_by": "owner",
  "accepted_at": "2026-09-24T12:00:00+08:00",
  "files": [
    {"path": "model/model3.json", "sha256": "64 lowercase hex characters"}
  ]
}
```

此 README 可進 Git；下載的資產和包含個人授權紀錄的 manifest 留在本機。

## Cubism Web 5-r.5 / Haru

Owner 接受適用條款並從官方頁面下載 `CubismSdkForWeb-5-r.5.zip` 後，可從 repo root
以單一命令重建本機 renderer：

```bash
uv run python scripts/prepare_live2d_renderer.py ~/下載/CubismSdkForWeb-5-r.5.zip
```

腳本會先核對已驗證的 ZIP SHA-256，再安全解壓至 Git ignored `models/`、加入 SIRO body
WebSocket bridge、執行官方 TypeScript sample 的 lockfile build，並為 Core 與 Haru 產生本機
`asset-manifest.json`。若目標已存在，只有明確加入 `--force` 才會重建。啟動整合 gateway：

```bash
SIRO_LIVE2D_DIST="$PWD/models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo/dist" \
  uv run siro-gateway
```
