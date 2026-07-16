# Codex Token Monitor for ESP32-S3-RLCD-4.2

基于 [CEJXXX/token-monitor-RLCD](https://github.com/CEJXXX/token-monitor-RLCD) 改造，硬件保持不变：
Waveshare ESP32-S3-RLCD-4.2、板载 SHTC3、Wi-Fi。

屏幕现在显示：

- Codex 周期额度剩余百分比与重置倒计时；
- 今日 Codex tokens、最近任务 tokens、当前计划；
- 北京实时天气、体感温度、湿度、风速；
- 本地时间、日期和板载室内温湿度。
- 单色 Codex 标识、动态天气图标，以及体感/湿度/风速状态图标。

## 数据链路

```text
~/.codex/sessions/**/*.jsonl        Open-Meteo（免 key）
              \                         /
               \                       /
                Python bridge :7777
                         |
                  GET /api/usage
                         |
              ESP32-S3 + LVGL dashboard
```

Bridge 只读取 Codex 会话日志里的 `token_count.rate_limits` 和 token 汇总，不读取登录凭据，
也不会把 Codex 认证信息发到网络。OpenAI 面向用户公开的是 Usage 页面；本工程使用本机客户端
已经写入会话日志的同一组百分比数据。日志格式属于本地实现细节，Codex 升级后若字段变化，
只需调整 `bridge/sources/codex_local.py`，固件协议保持不变。

## 1. 启动 Bridge（Windows）

安装 Python 3.10+ 或 [uv](https://docs.astral.sh/uv/)，然后在 PowerShell 中：

```powershell
Copy-Item bridge\.env.example bridge\.env
# 编辑 bridge\.env，至少替换 RLCD_AUTH_TOKEN
scripts\start-bridge-windows.ps1
```

Windows 启动脚本会读取 `bridge/.env`。也可以在当前终端临时覆盖环境变量：

```powershell
$env:RLCD_AUTH_TOKEN = '换成你自己的长随机串'
$env:RLCD_HOST = '0.0.0.0'
scripts\start-bridge-windows.ps1
```

验证接口：

```powershell
Invoke-RestMethod 'http://localhost:7777/api/usage?mock=1' `
  -Headers @{ 'X-RLCD-Token' = $env:RLCD_AUTH_TOKEN }
Invoke-RestMethod 'http://localhost:7777/api/usage' `
  -Headers @{ 'X-RLCD-Token' = $env:RLCD_AUTH_TOKEN }
```

## 2. 配置、编译与烧录

从开始菜单打开 ESP-IDF 5.x PowerShell：

```powershell
Set-Location firmware
Copy-Item main\secrets.h.example main\secrets.h
notepad main\secrets.h
idf.py set-target esp32s3
idf.py build flash monitor
```

`main/secrets.h` 里填写：

- 2.4 GHz Wi-Fi SSID 与密码；
- 运行 Bridge 的电脑局域网 IP，例如 `http://192.168.1.42:7777/api/usage`；
- 与 `RLCD_AUTH_TOKEN` 完全相同的 token。

首次建议把 URL 改成 `.../api/usage?mock=1`，确认布局后再切回实时接口。

## 3. 自检

```powershell
Set-Location bridge
python -m unittest discover -s tests -v
```

## 适合继续加到这块屏上的内容

按实用性排序，我建议：

1. 空气质量（AQI / PM2.5）——北京比降水概率更值得占固定位置；
2. 未来 3 小时降水概率——只在有雨时替换风速，减少常态噪音；
3. GitHub 待处理 PR/CI 数——适合工作台，但需要 GitHub token，建议做可选模块；
4. 今日专注时长或下一场会议——个人价值高，但会引入日历授权；
5. Bridge/Wi-Fi 最后更新时间——可作为角落里的故障提示，不必常驻大字。

当前版本优先保持零天气 API key、零 Codex 凭据抓取、局域网即可运行。

Codex 标识参考自 [OpenAI 官方 Codex 页面](https://openai.com/codex/)；OpenAI、ChatGPT
及相关标识为 OpenAI 的商标。本项目中的单色版本仅用于个人硬件状态屏显示。

## 安全

Bridge 监听 `0.0.0.0` 时务必设置 `RLCD_AUTH_TOKEN`。不要把 7777 端口直接暴露到公网。
仓库中的 `bridge/.env` 和 `firmware/main/secrets.h` 已加入 `.gitignore`。

上游项目使用 MIT License；本改造保留相同许可边界。
