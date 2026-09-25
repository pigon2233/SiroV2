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
