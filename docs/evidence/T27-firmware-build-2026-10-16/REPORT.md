# T27 ESP32 完整 cross-compile 驗收

日期：2026-10-16（Asia/Taipei）。結果：**BUILD_VERIFIED / HARDWARE PENDING**。
本次將原「沒有 PlatformIO，未跑完整 firmware build」缺口轉為實際 pinned `esp32dev` 編譯通過；不是燒錄、真 NTP、GPIO 或目視 LED 通過。

## 範圍與實際輸入

- 主 repo HEAD 核對為 `940bdb707649ac3a58373c9527683d39f9b9e111`（既有 commit，本代理未建立）。
- 只讀 `firmware/esp32/src/main.cpp`、`platformio.ini`、`include/secrets.example.h`；完整 SHA256 在 `metadata.json` 與 `cleanup.json`。三者前後完全一致。
- 只複製三個明確檔到自有 `/tmp` project，example 原封不動複製為 compile-only `include/secrets.h`。沒有讀取實際 secrets、改 production、改 pins／repo dependencies、連 Broker／serial、刷板或全域安裝。
- 在 owned temp venv 安裝明確 `platformio==6.1.19`；隔離 `PLATFORMIO_CORE_DIR`、pip cache，關閉 telemetry。全程 `pio run --project-dir <owned-project> --environment esp32dev --jobs 2`，未使用 upload target。

## 兩次執行結果

| 執行 | 實際結果 |
|---|---|
| 首次 | 314.308s，工程預算 2GB 在 framework unpack→copy 雙副本階段觸發；監控 SIGTERM，exit -15／temp-cap。停止時 2,323,702,076 logical bytes，尚未開始 compiler，不算 compiler FAIL 或 PASS。完整 log/json 保留。 |
| 重啟前 | 原 process group 已消失；目的 framework 缺 package.json，確定是 partial install。只移除自己的 partial destination 730,530,983 bytes 與 staging 771,573,491 bytes。三個已下載 archive 的實際 SHA256 均核對官方 registry 相符，保留 cache。 |
| 完整重跑 | Root 明確批准工程預算升為 3GB；500MB public download 預算與總 active build 900s 不變。從 cache 乾淨重裝，**EXIT 0 / 529.253s**（PIO 自報 527.84s）。兩輪 build-process active 共 **843.561s**。完整 compile、link、size check、ESP32 image 成功。 |

重跑 observed logical peak 1,935,710,699 bytes，完成 1,662,108,836 bytes／du 1.6G；1 秒採樣不宣稱精確瞬時 peak。
首次工程預算停止完整保留，不改 source／SDK pin 來繞過 compiler。公共 cryptography wheel 下載曾 reset 兩次，由 pip 原有有界 retry 成功；非 firmware 編譯錯誤。

## 已解析版本與輸出

- PlatformIO Core 6.1.19，Python 3.14.4，Linux x86_64。
- espressif32 6.12.0；framework-arduinoespressif32 `3.20017.241212+sha.dcc1105b`（Arduino 2.0.17）；Xtensa `8.4.0+2021r2-patch5`；esptool package `2.40900.250804` / 4.9.0；SCons package `4.40801.0`。
- 原 pinned ArduinoMqttClient 0.1.8、ArduinoJson 7.4.2，不改 project dependency。
- RAM **45,276 / 327,680 bytes (13.8%)**；Flash **777,901 / 1,310,720 bytes (59.3%)**。
- firmware.bin **784,480 bytes**、firmware.elf **11,716,732 bytes**；另有 bootloader／partitions。實際 artifact SHA256 在 `compile-results.json`，`firmware-elf-header.log` 證實 ELF machine 為 Tensilica Xtensa。這些 hash 僅識別本次實際輸出，不宣稱跨路徑／工具版本 bit-for-bit reproducible。
- 七個實際 public PIO archive 共 **341,577,725 bytes**，全部實際 SHA256 等於官方 registry metadata；pip cache 約 **10,172,172 bytes**。未量測 HTTP 重送／header 的網路 wire bytes，不將 cache 大小冒稱精確流量。原 <500MB 工程下載預算未出現超界跡象。

安裝方式與隔離已核對 [PlatformIO 官方 pip／CI 說明](https://docs.platformio.org/en/stable/core/installation/methods/pypi.html)，版本／license 來源為 [PyPI Core 6.1.19](https://pypi.org/project/platformio/6.1.19/)。Arduino／toolchain 解析沿 [官方 pinned platform manifest](https://raw.githubusercontent.com/platformio/platform-espressif32/v6.12.0/platform.json)。

成功 build 後額外刷新四個小 package registry metadata 時曾遇有界 HTTPS handshake timeout，未更改成功 build 結果。改讀本次 PIO 自身已保留的官方 registry cache，即可完成七個 archive 核對；沒有為後置查詢繼續等待網路。

## 清理與仍待驗

兩輪 PIO process groups 均已不存在；owned venv／SDK／toolchain／pip cache／compile-only secrets／ELF／bin／project 全部移除，1,662,108,836 logical bytes 回收；global ~/.platformio 仍不存在。只保留本 evidence 小文字檔，沒有將可誤刷的 synthetic firmware binary 搬入 repo。

真 Broker、實板配網／NTP／GPIO／手動改燈／LED readback、A18 HARDWARE PENDING 均保持。完整 firmware build 只能證明目前 pinned target 可以編譯與 link，不能替代設備協定及人工實板驗收。父代理負責更新共享 STATUS／README／task；本代理沒有改主 repo。
