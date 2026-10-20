# SIRO VRM 模型：可編輯工程與產生鏈

擁有者決定（2026-10-20）：VRoid 工程檔放進 repo。repo 沒有 Git LFS；這個檔 8.4 MB，
是目前 repo 最大的單檔（原本最大約 2.9 MB）。推送前請確認可以接受這個大小。

## 產生鏈

| 步驟 | 檔案 | SHA-256 | 大小 | 在哪裡 |
| --- | --- | --- | --- | --- |
| 1. VRoid Studio 工程（可編輯） | `model/siro-v2.vroid` | `255089ede6b4cebb98b295040f2e874987c1844f2f819216d10e7a2cb6db7901` | 8,418,234 | 本 repo |
| 2. VRoid Studio 2.14.0 匯出 VRM 1.0 | `SIRO V2.vrm` | `339a15bafb9f17bf2a7b283895fe563fa4ef1d0b26ee22a588ddb7d6e6dc37b0` | 16,507,936 | 擁有者電腦 `siroClaude/`，不在 Git |
| 3. Blender 加髮夾後重新匯出 | `SIRO V2 blender.vrm` | `c49e8baf1fff659ce2d63f0ccf647d461f23f0c265b920f9232589bb1ff7a404` | 17,523,104 | 同上 |
| 4. `scripts/tune_vrm_springs.py` 加衣物碰撞 | `SIRO V2 blender colliders.vrm` | `5ae8be54853029b6b20bb847570b7b1139b47b2ed7a2d1b54b3df8f74024d5e2` | 17,523,376 | 同上；註冊為 Git-ignored `config/body-assets/siro-vrm/model.vrm` |

第 4 步的雜湊與目前註冊的 `model.vrm` 及其 `asset-manifest.json` 相同（2026-10-20 核對）。

## 第 3 步做了什麼（從檔案比對得知）

比對第 2、3 步的 glTF JSON：產生器改為「VRM Add-on for Blender v4.10.2 with Khronos glTF Blender I/O
v5.2.40」；多了一個 `HairClip` mesh、材質 `HairClip_MAT` 與一張貼圖；表情多了 `lookUp/Down/Left/Right`；
節點順序與 skin 重新編排。Blender 工程（.blend）沒有保存，所以**只靠 .vroid 無法重現髮夾**。
擁有者 2026-10-21 交由 Claude 決定，決定是：第 3 步的 VRM（17.5 MB）不放進 repo，只記雜湊。理由：它和
第 4 步的執行用模型幾乎一樣大，再加一份會讓 repo 多 17.5 MB，而髮夾只是一個小 mesh；檔案仍在擁有者電腦
`siroClaude/`，用上表的雜湊可以確認拿到的是同一份。

要修改目前模型，可以：

- 改外觀、服裝、髮型：在 VRoid Studio 開 `.vroid` → 匯出 VRM 1.0 → 在 Blender（VRM Add-on）匯入，
  重新加上髮夾 → 匯出 → 跑第 4 步。
- 只改髮夾或小地方：在 Blender 直接匯入第 3 步的 VRM（VRM Add-on 可往返）→ 匯出 → 跑第 4 步。

第 4 步之後照常安裝：

```
uv run python scripts/tune_vrm_springs.py "<第 3 步.vrm>" "<輸出.vrm>"
uv run python scripts/prepare_vrm_renderer.py --model "<輸出.vrm>" --license-url https://vroid.com/en/studio/terms
```

## 授權與發布

- 模型是擁有者在 VRoid Studio 自製。VRM meta：`commercialUsage: personalNonProfit`、
  `allowRedistribution: false`、`avatarPermission: onlyAuthor`。這和動作包的非商用限制一致。
- VRM 本身（第 2–4 步）不進 Git：repo 只放可編輯的 .vroid、碰撞腳本與雜湊；執行用的 VRM 由
  `prepare_vrm_renderer.py` 註冊到本機。若 repo 之後公開，.vroid 等同公開模型原始檔，請先確認。
