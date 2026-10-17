# D65 / T15 動漫角色聲試聽

2026-10-17，既有 dirty 工作區續作；沒有改 production、wrapper、專案 lockfile 或私人資料。使用者真人回報 Kokoro 機械、音色不好及破碎，指定「動漫感、可愛活潑」。本輪交付三段實際本機生成的短試聽，**待使用者聽選**；D64 播放／取消功能通過不能代替品質通過。

## 實際產出

同一合成台詞：「嘿，你回來啦！我是希洛，今天也要元氣滿滿喔！有什麼新鮮事，快來跟我分享吧！」音檔位於本機 ignored `.siro-data/wsl-setup/voice-quality`，不加入 Git；完整提示詞、seed、hash、環境 freeze 和檢查結果見 [RESULTS.json](RESULTS.json)。角色為原創合成女聲，沒有錄製真人或模仿指定人物。

| 試聽 | 描述目標 | 秒數 | 生成秒數 | token／終止 | PCM peak／削波數 |
|---|---|---:|---:|---|---|
| A-energetic.wav | 清亮、元氣、活潑可愛 | 8.56 | 14.599 | 108／EOS，未達512 cap | 0.5117／0 |
| B-sweet.wav | 甜柔、溫暖、親切 | 8.00 | 11.498 | 101／EOS，未達512 cap | 0.4824／0 |
| C-playful.wav | 俏皮、靈動、好奇 | 7.84 | 12.089 | 99／EOS，未達512 cap | 0.5195／0 |

真 RTX3050／Qwen VoiceDesign 生成，24kHz單聲道 PCM16；載入3.942s，峰值 PyTorch allocated約4.45GB（不是整機顯存）。三段有限、raw over-full-scale0、PCM saturation0；只加5ms頭尾fade，必要時才衰減至0.8峰值，本次gain均1.0，沒有變調或提高速度偽裝角色聲。完整一段生成，不使用正式介面的分段播放。

真本機 Whisper CPU 合成音檔 sanity check：三段 final且worker不忙，耗時4.224／2.900／2.858s，主要台詞可辨。A／B省略「嘿」，C還省略「也」，以及喔／啊等差異如實保留；ASR正確率、自然度、動漫感和破音聽驗均不能由這些輸出推導通過。

## 舊聲線與破音診斷

原 Kokoro `zf_xiaobei` 用已知合成台詞測 raw float與PCM16。energy0.5：raw peak0.74395，PCM peak0.55795；energy1.0：PCM peak0.74393。均有限、over-full-scale0／PCM saturation0。這個反例沒有證明音量削波是使用者破音的根因，也不能排除模型感知失真、正式分段接縫、WebKit／Pulse或Windows播放環境。因此沒有盲目改音量、聲稱破音已修好或忽略使用者聽感。新三段完整檔案也供使用者比較是否仍有破碎聲。

## 來源、安裝與隔離

官方 [Qwen VoiceDesign model](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) Apache-2.0，固定revision見RESULTS；所有下載檔案依上游LFS SHA256或Git blob核對。模型含3.833GB主權重、0.682GB tokenizer，留在E槽Ubuntu VHD的 `~/.local/share/siro/assets/voice-auditions/`。下載原始碼／模型與執行期分離，載入固定本機目錄、local_files_only／offline；本機audit guard紀錄推論連線嘗試0，這是Python guard而非OS network namespace證明。

依[官方 SDK API](https://github.com/QwenLM/Qwen3-TTS)及[官方 PyTorch 發布](https://pytorch.org/get-started/previous-versions/)準備隔離 Python3.12 環境 `~/.local/share/siro/voice-design-py312`，SDK0.1.1、Torch／torchaudio2.8.0、Transformers4.57.3、accelerate1.12.0。完整freeze已記錄，不更動正式環境或假裝正式專案lock包含此試聽環境。首次CUDA index的cuDNN下載timeout，保留 `install-cuda-index-failed.log`，相同版本官方PyPI發布安裝後成功。使用SDPA，不編譯FlashAttention；SDK的FlashAttention及SoX CLI警告保留，沒有為不阻擋VoiceDesign的警告擴大系統修改。

推論程序已正常exit0，三個ASR短生命worker退出；最後GPU使用約2.2GB，沒有常駐額外模型、卸載Ollama或關閉桌寵。只讀公開模型與合成音檔，沒有麥克風／私聊／原錄音／外部TTS請求。

## 已跑命令及接續

本機保留的重現腳本（ignored）如下，官方依賴與模型manifest、固定提示詞／seed／EOS觀察結果可由RESULTS核對：

```powershell
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/prepare_anime_voice.py metadata
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/prepare_anime_voice.py provision
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/prepare_anime_voice.py download
wsl -d Ubuntu -- env OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/inspect_voice_quality.py
wsl -d Ubuntu -- env OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 /home/pepepig/.local/share/siro/voice-design-py312/bin/python .siro-data/wsl-setup/audition_anime_voice.py
wsl -d Ubuntu -- /home/pepepig/.local/share/siro/voice-validation-py312/bin/python .siro-data/wsl-setup/check_anime_auditions.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/publish_anime_auditions.py
git check-ignore .siro-data/wsl-setup/voice-quality/A-energetic.wav .siro-data/wsl-setup/voice-quality/B-sweet.wav .siro-data/wsl-setup/voice-quality/C-playful.wav
git diff --check
```

實際生成、EOS／cap／波形檢查、3段ASR、metadata出版與Git ignore確認均exit0。未跑本輪全pytest／scripts/check／CI；沒有production變更，不把這些未執行檢查列PASS。

下一步由使用者聽A／B／C、選聲線及回報破音；選定後沿官方「Voice Design then Clone」流程固定角色聲，接入既有可取消worker並重驗播放、晚到輸出fence及單一audio owner。此流程尚未實作／部署，生成耗時也不符合或證明首音SLO；**主觀品質與正式接入仍未完成**。
