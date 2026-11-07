# RO V2 Aggressive LT — 一次运行包

这是新的四股集中策略，不能套用之前六股 V2_REGIME_LT 的 +13.26% 结果。

## 一次运行

1. 如果旧 T1 的 Watcher/循环仍运行，先在 T1 按 Control+C 停止，保留全部 checkpoint/凭证。不要关掉 T2。
2. 下载本 ZIP 到 Downloads。
3. 在 T2 当前 starter-kit 目录、原 .venv 环境里执行一次：

```bash
unzip -qo ~/Downloads/RO_V2_AGGRESSIVE_ONE_CLICK.zip -d ~/Downloads && python ~/Downloads/ro_v2_aggressive/start.py --live
```

**--live 会在全部检查通过后自动开始向 Official 模拟比赛提交决策。**

依次自动完成：补齐缺少的依赖、跑本机官方代码接口测试、审查历史数据时间戳、回测固定的激进策略、检查账户/实时完整日行情/官方格式、启动长期循环。无需逐步截图确认。

检查失败就停止，并自动打开报告文件夹；不会改用另一策略，也不会绕过官方 Checkpoint 的锁或恢复限制。重跑同一命令保留原始提交；不要删 Checkpoint。没有自动提交 Final。

Mac 须开机、联网、保留终端、保持屏幕展开。程序使用 caffeinate 防止空闲睡眠，不保证合盖、断电、系统重启后继续。Control+C 正常停止。不会安装后台登录服务，也不会修改原 V1 文件。

## 激进规则

- 正常强势环境，目标股票仓位 100%，最多四股 30%/28%/24%/18%。
- 60/20/5 日动量评分保留趋势和波动惩罚；仅正趋势股票入选。
- 市场广度低于 50% 时目标规模 85%，低于 35% 时 65%；有效个股不足时实际仓位可能更低，全部不合格时现金。
- 同一组目标上限 60%。价格自然漂移可能改变现有持仓；30% 限制用于提交目标。
- 常规换仓在每周首次交易日的 R1 检查；每天 R1 可进行风险减仓/上限修正。
- R2–R7 明确不提交以保持原股数。这是有意 HOLD，不是自动化漏单。
- 激进是集中度与上涨行情下高仓位，不是杠杆、无限交易或保证盈利。

## 研究检查

读取 ~/Downloads/hourly_market_data_2021_2026.zip。只固定比较 V1、已测六股低换手、四股激进版；2021–2024 开发期、已查看的 2025 复核期；每个都测试 10/20bps。

粗略启动门槛：激进版四个“时期×成本”组合净收益 >0、Sharpe >0、最大回撤 <=35%。这只是提前写定的诊断门槛，不是科学证明或独立样本外验证。未通过会停止。没有扫描参数、按 2025 收益反复优化或静默降低激进程度。

数据时间检查要求时间戳/交易日一致、全部小时栏在 ET 09:30–15:30 范围内，至少 99% 股票交易日首栏是 09:30。不能核验数据商调整价公式；短历史、股票池选择偏差、每日一次成交与官方七轮计分区别仍存在。

## 输出与状态

运行报告：starter-kit/private/ro_v2_aggressive/run_日期时间/

- run.log：运行、自检、错误日志。
- research/backtest_metrics.csv、summary.json：新激进版的真实本机回测结果（不是包内合成结果）。
- research/data_audit.json：历史时段检查。
- runtime.json：程序及官方客户端 SHA256。
- STOPPED.txt：只有出错时存在。

持久状态：starter-kit/private/ro_v2_aggressive/strategy_state.json

市场缓存：starter-kit/private/ro_v2_aggressive/market/

提交仍由本机官方 OriginalSession 负责，默认复用 .icaif/checkpoint.json 与 .icaif/credentials.json。若你的旧命令用自定义路径，应在同一命令前设置 RO_CHECKPOINT / RO_CREDENTIALS 为原路径；不要新建或复制状态规避占用。

### 看见什么算成功

- TESTS_PASS：本机测试通过，还没有实盘/模拟比赛提交证据。
- LOCAL_RESEARCH_GATE_PASS：本机历史诊断通过，仍不是收益保证。
- PREFLIGHT_PASS：真实账户、完整行情、官方格式检查通过；这一检查不上传。
- OFFICIAL_RUNNING：循环已启动，不代表 R1 被接受。
- RECEIPT_VALID official-... submission=真实ID：官方回执确认有效；不等于执行已完成。
- HOLD_NO_UPLOAD：保持股数，无上传，不产生本次调仓。
- TRADING_COMPLETE_FINAL_REQUIRED：交易期结束，还需手动准备 Final 材料。

## 完成了什么、还不能保证什么

包内测试直接调用下载的官方 Watcher 类，用模拟服务边界检查 HOLD 零上传、合法决策、占用轮次、过期轮次、原始 ID 恢复、未来日线剔除、持仓上限、状态恢复。它们不是用真实 token 测试服务器。合成 Parquet 的端到端测试仅用于验证程序运行，不用于判断收益。

本机启动将再次对你实际安装的官方代码跑相同测试。尚未在你的 Mac 上实际运行过这个新包，不能保证网络、数据源、账户字段或服务器行为一次成功。失败默认停止并保留原始状态，避免用猜测继续交易。

研究 HOLD 为“不下单”，本适配器通过明确的本地 HOLD 异常中止官方 Watcher 的上传路径，实现相同股数保持。常规策略只运行 R1，提交的既有持仓权重取官方提交时快照，与历史前一收盘价并不完全相同，因此实际路径不会逐点等于日频回测。

市场数据来自 Yahoo Finance/yfinance 调整日线；无 LLM 推理调用、无 OpenAI API 费用。最终复现材料应记录代码辅助开发及数据源，按照官方要求披露。

官方来源与本次检视版本：
https://github.com/DeepIntoStreams/2026ICAIF_Trading_Agent_Competition
commit 39cc9acfa2f1c33c3213086b83847c07bd7493bb

只使用你原先的官方客户端；包内未捆绑或替换其上传恢复代码。
