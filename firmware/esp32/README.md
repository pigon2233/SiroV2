# SIRO ESP32 MQTT 範例

狀態：source ready，尚未在實體板或 PlatformIO toolchain 編譯／燒錄。

此範例使用 ESP32 DevKit 內建 LED（預設 GPIO 2）作低風險 actuator。複製
`include/secrets.example.h` 為被 Git 忽略的 `include/secrets.h`，設定 Wi-Fi、loopback/LAN MQTT
broker、每台裝置獨立帳密與 `SIRO_DEVICE_ID`，再執行：

```bash
pio run
pio run --target upload
pio device monitor
```

topic：`siro/devices/{id}/{state|availability|command|ack}`。availability/state retained；command/
ack 不 retained。LWT 為 retained `offline`。firmware 明確拒絕 retained command、過期 command、
重複 command ID 與非 `light.set` action；ack 後另發 state，gateway 必須以 state readback 判定成功。

接線：使用板載 LED 時不需外接。改用外接 LED 時，GPIO → 220–330 Ω 電阻 → LED 陽極，LED
陰極 → GND；依板型修改 `SIRO_LED_PIN`。不可直接驅動市電、馬達或大電流負載。

正式 LAN 部署需 TLS 或隔離可信網段、每設備 ACL 與可撤銷憑證。此 simulator broker 僅綁
127.0.0.1，不代表明文帳密適合 LAN。
