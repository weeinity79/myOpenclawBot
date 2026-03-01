# 美股量化炒股软件开发计划（个人/小团队）

> 目标：从研究到实盘，逐步上线；强调模块化、可迭代、可审计、可控风险。

---

## Changelog
- 2026-03-01 round7：修复 DOC-TRACE-001（BUG ID 冲突）：将 BUG 标签改为命名空间方案（BUG-CASH/BUG-CA/BUG-UNIV/BUG-EXEC/BUG-DATA），并更新全文引用与验收测试标题，确保全局唯一且稳定。
- 2026-03-01 round6：修复 QA round5 遗留高优 BUG：1) Paper/Live 拆股完全券商权威（禁止 engine_apply_once），拆股公告但券商未更新时冻结该标的交易；开盘后强制对账，若不一致则停盘并需人工介入。2) 拆股幂等键禁止使用 float ratio，改为 canonical ratio（分子/分母整数或规范化小数字符串）；优先使用券商 corporateActionId，并补充相应验收测试。
- 2026-03-01 round5：拆股处理 v1 补充幂等规则（Paper/Live 券商权威，防 double-apply）+ 增加“券商已调整持仓”验收测试；补充反向拆股零股/cash-in-lieu v1 政策与 1-for-5 验收测试。
- 2026-03-01 round4：补充公司行为 Corporate Actions / Splits Handling v1：在未复权价格口径下处理拆股（share 数按比例调整、平均成本反向调整、净值连续），并增加拆股连续性验收测试。
- 2026-03-01 round3：修订 BUG-DATA-01/BUG-EXEC-01（并补充 BUG-UNIV-02 备注）：v1 统一回测/纸交易/实盘的成交与估值价格口径为未复权 OHLC（禁止回测用 Adj Close 做 NAV）；下单时间与 next_open 成交模型对齐为 09:30 ET（开盘）；缺失数据估值补充可选保守折价。
- 2026-03-01 round2：修订 BUG-CASH-01/BUG-UNIV-01/BUG-EXEC-02：现金账户 T+1 结算与可用现金口径（防 GFV）+ 验收；Universe v1 明确退市/缺失数据/符号生命周期与验收；执行模型 v1 统一为 next_open + bps 成本（不依赖分钟数据）。并补充：ADV$ 使用未复权价计算、回测股息/NAV 口径 v1。
- 2026-03-01：补齐阶段门验收标准（PoC/MVP/Beta）、日频执行假设 v1（回测=纸交易）、风险硬约束与 MaxDD 策略、Universe v1 过滤与版本化、仓位/止损模型（Position Sizing v1）、OMS 幂等与稳定性验收、免费数据双源校验与复权/股息处理建议。

---

## 1) 范围定义（Scope）

### 目标市场
- 美股：NYSE / Nasdaq
- 交易时段：常规盘（9:30–16:00 ET）；盘前/盘后作为可选扩展（需单独风控与流动性约束）
- 币种：USD

### 频率两套方案
- **A. 中低频（日/周）—推荐先做**
  - 数据粒度：日线 OHLCV（必要），可选 1h/4h
  - 交易频率：每日盘后出信号，次日执行；或每周再平衡
  - 优点：工程复杂度低、滑点敏感度低、对基础设施要求低、容错高
- **B. 日内（可选扩展）**
  - 数据粒度：1m/5m（必要），可选 tick（逐笔）用于更精细回测/撮合
  - 交易频率：分钟级评估/下单；需要更严格延迟、风控、监控

### 资产范围（硬约束 v1）
- **ETF-only（仅交易 ETF）**
- **Long-only（只做多）**
- **现金账户（Cash account），不做融资融券**
- **不使用杠杆（No leverage）**

### Cash Settlement Policy v1（现金账户结算口径，防 GFV）
- 适用：美国股票/ETF **T+1 结算**（v1 固化为 T+1；若券商/品种不同需配置）。
- 账户字段（必须在 Portfolio/OMS 中显式建模并落库）：
  - `settled_cash`：已结算现金（可用于买入）
  - `unsettled_cash`：未结算现金（来自当日卖出，结算前不可用于买入）
  - `reserved_cash`：已下单但未成交/未确认的现金占用（防止重复下单超买）
  - `available_cash = settled_cash - reserved_cash`
  - `equity = settled_cash + unsettled_cash + positions_mkt_value`（净资产口径）
- 买入约束（Hard）：任何 **Buy** 订单在发单时必须满足 `order_notional <= available_cash`。
  - v1 明确：**不允许使用当日卖出产生的 unsettled_cash 去买入**（避免 Good Faith Violation/GFV 风险）。
- 卖出处理：卖出成交后，现金先计入 `unsettled_cash`，在 `T+1` 开盘前（或券商结算回调到达时）转入 `settled_cash`。

**BUG-CASH-01 Acceptance Tests（必须自动化）**
1) **GFV 阻断**：T 日 `settled_cash=10,000`，先 Buy $10,000 成交后当日再 Sell 全部，随后尝试再次 Buy $10,000（仅依赖卖出回款）。期望：第二次 Buy 被系统拒绝，错误码/日志包含 `INSUFFICIENT_SETTLED_CASH`。
2) **结算后放行**：同场景，推进到 T+1（触发结算过账），再次 Buy $10,000。期望：允许下单且 `settled_cash` 扣减正确。

### 风险约束 v1（硬限制 + 触发动作）
- **组合最大回撤（Hard）：MaxDD = 10%**
  - 触发动作（触发日收盘后评估）：
    - 立即进入 **Risk-Off 模式**：新开仓=禁止；只允许减仓/平仓；目标仓位缩到 0–30%（默认 0%）
    - **冷却期（Cooldown）= 10 个交易日**：冷却期内即使信号恢复也不加仓
    - **恢复条件（Recovery）**：冷却期结束且当前回撤 < 6%（从峰值回撤恢复）才允许逐步加仓（例如 3 天线性从 30% → 100%）
- **单笔风险（Hard）：每笔最大亏损 ≤ 0.5% NAV**
  - 用止损距离（例如 ATR*n 或固定 %）反推仓位（见 Position Sizing Policy v1）
- **单一持仓上限（Hard）：单 ETF 市值 ≤ 20% NAV**
- 备注：此版本不做行业/主题敞口限制（ETF 已含分散），后续可加。

---

## 2) 架构设计（模块化，可逐步上线）

建议按“数据→研究→回测→实盘→监控审计”五条主链路拆分，统一用**事件与版本**串起来。

### 2.1 数据层（Data Ingestion，免费数据优先）
- 行情：日线 OHLCV；日内则 1m/5m；可选 tick
- 关键：统一时间轴（UTC 存储）、数据版本化（snapshot/data build id）、质量校验（缺失/尖刺/复权一致性）

**免费数据处理建议 v1（必须写入工程规范）**
- **双源校验（2-source validation）**：同一标的同一日期的 close/volume 至少用 2 个来源比对（例如：Stooq + Nasdaq Data Link/AlphaVantage/Polygon free tier（若可用）/IBKR 历史数据）。差异超阈值（如 |ret|>50bp 或成交量差>20%）标记为 `data_quality=warning` 并阻断当日交易（默认）。
- **价格口径（BUG-DATA-01，必须统一）**：v1 在**成交价建模 + 持仓估值 + NAV 计算**上，回测/纸交易/实盘统一使用**未复权（unadjusted）OHLC**。
  - 研究/因子：可用 Adj Close（或复权因子）做总回报特征，但**不得**用 Adj Close 去做回测 NAV/持仓估值（否则与券商未复权成交/估值口径不一致）。
- **分红/公司行为（v1 简化）**：
  - 纸交易/实盘：以券商回报的 dividend/cash movements 为准，现金分红计入 `settled_cash`（到帐日），并落库可追溯。
  - 回测：v1 可先**不模拟现金分红入账**（免费数据股息不全时避免伪精确），则回测净值为**price-return**（价格回报）口径；报告必须注明与券商“total return”可能有偏差。

**Corporate Actions / Splits Handling v1（拆股/反向拆股处理，未复权价口径）**
- 目标：在 **未复权 OHLC** 估值/成交口径下，拆股不应凭空产生收益或亏损；应保持持仓市值与 NAV 的**连续性**（忽略成交与真实市场波动）。

### Single Source of Truth（关键：避免纸交易/实盘拆股重复应用）
- **Backtest（引擎自洽）**：以引擎内部 `split_event` 为唯一事实源（来自数据源 corporate action 或由 price factor 推导）。拆股只由引擎在“effective date 开盘前”应用一次。
- **Paper/Live（券商权威，v1 推荐）**：以**券商 position snapshot / corporate action 回报**为唯一事实源。
  - v1 规则：**纸交易/实盘禁止“再对券商已调整后的持仓”做二次换算**。
  - 引擎仅做：对账、记录事件、保证 NAV/成本口径可追溯。

### 会计规则（拆股生效日 effective date 的开盘前应用）
- 设拆股比例为 `r`（例如 2-for-1，则 `r=2`；1-for-5 反向拆股，则 `r=0.2`）。
- 若由引擎应用（Backtest/内部重放）：
  - `shares_new = shares_old * r`
  - `avg_cost_new = avg_cost_old / r`
  - `position_cost = shares * avg_cost` 在拆股前后应保持不变（仅单位变化）。

### Idempotency Guard（幂等防护：防止 double-apply）
- 所有链路必须落库 `split_event(symbol, effective_date, action_type, ratio, ratio_canonical, source, broker_ca_id?, detected_at, applied_at, apply_mode, status)`。
- **canonical ratio（必须）**：幂等/对账/日志中禁止使用 float 做键值或比较口径。
  - 推荐表示 1（优先）：`(ratio_num, ratio_den)` 整数对（例如 2-for-1 → `(2,1)`；1-for-5 → `(1,5)`）。
  - 推荐表示 2：规范化小数字符串 `ratio_dec_str`（例如 `"0.2"`，去掉多余尾随 0，统一小数点）。
  - 内部计算可用 Decimal，但落库与幂等键必须用上述 canonical 表示。
- **唯一键（建议）**：
  1) 若券商提供 `corporateActionId` / `broker_ca_id`：**必须**以 `(broker_ca_id)` 作为主幂等键（跨系统最稳）。
  2) 否则使用 `(symbol, effective_date, action_type='SPLIT', ratio_num, ratio_den, source)`（或 `ratio_dec_str`）。

### Paper/Live Split Handling v1（券商权威 + 冻结交易 + 强制对账）
> 目标：消除 `engine_apply_once` 的时序竞态（拆股公告已知但券商尚未更新 positions 的时间窗），避免 Paper/Live 出现“引擎先改、券商后改/回滚”导致 shares/avg_cost/NAV 乱序。

- **硬规则（v1 简化）**：Paper/Live **禁止** `apply_mode='engine_apply_once'`。
  - Paper/Live 的 shares/avg_cost 只允许来自券商 `positions_snapshot`（或券商 corporate action 回报后的 snapshot）。
  - 引擎只做：记录、对账、冻结/解冻交易、审计。
- **拆股公告但券商未更新（Pending CA 窗口）**：若本地检测到 `split_event(status='announced'|'expected')`，但券商 snapshot 仍是 pre-split shares，则：
  - 将该标的置为 `trade_status='BLOCKED_CA_PENDING'`（冻结下单/撤改/换仓），直到满足以下任一条件：
    1) 拉到券商 snapshot 显示 post-split shares（券商已应用）；或
    2) 收到券商 corporate action 确认（含 `broker_ca_id`）并且随后 snapshot 对齐；或
    3) 人工确认/干预（仅在极端情况下）。
  - 备注：冻结只影响该 symbol；组合其他标的可继续。
- **开盘后强制对账（Post-open reconciliation，broker wins）**：每日开盘后（例如 09:35 ET）必须执行：
  - 对每个有 pending/近期 CA 的 symbol：比较本地 ledger（上次已确认 snapshot）与券商最新 snapshot 的 `(shares, avg_cost, cost_basis)`。
  - 若不一致（超出容忍度）：
    - 立即将该 symbol 置为 `trade_status='HALT_RECON_MISMATCH'`；
    - 记录 `risk_event/recon_event`（包含 broker snapshot 与本地差异、相关 split_event）；
    - **broker wins**：不允许自动“猜测修复”；必须人工介入（确认券商最终口径后再解冻）。

### Reverse Split Fractions / Cash-in-Lieu Policy v1（反向拆股零股与现金替代）
- v1 选择：**broker-authoritative**。
  - 若券商回报的 post-split position 含 fractional shares（部分券商支持），引擎直接接受该 shares 为准。
  - 若券商回报为整数 shares + 一笔 `cash_in_lieu`（现金替代），引擎按券商现金流水为准并落库。
- 仅在 Backtest/内部重放必须自行处理时（不依赖券商现金流水）：
  - 若 `shares_old * r` 不是整数：
    - `shares_new = floor(shares_old * r)`（v1 固定向下取整；避免凭空增加股票）
    - `fractional = shares_old * r - shares_new`
    - 生成 `cash_in_lieu = fractional * ref_price`
      - `ref_price` v1 取 effective date 的未复权 `open`（或券商提供的 cash-in-lieu 价格/金额则覆盖）。
  - 记录一条现金流水事件：`cash_movement(type='CASH_IN_LIEU', symbol, effective_date, amount)`。
  - （可选，BUG-CA-03）回测/内部重放的成本分摊：将拆股前的总成本 `cost_old = shares_old * avg_cost_old` 按份额比例分配给 `shares_new` 与 `cash_in_lieu`（例如按 `shares_new` 对应的 post-split 等价份额与 `fractional` 份额占比），以保证 realized/unrealized PnL 可追溯；v1 用“按份额比例”即可。

**拆股处理 Acceptance Test v1（必须自动化）**
- **NAV 连续性（2-for-1）**：给定 D0 收盘：`price=100`，持仓 `shares=10`，`avg_cost=100`，无现金；D1 为拆股生效日，未复权价格跳变为 `price=50`（仅由拆股导致）。系统在 D1 开盘前应用 `r=2` 后应满足：`shares=20`、`avg_cost=50`，且在 D1 估值时 `position_value = 20*50 = 1000` 与 D0 的 `10*100 = 1000` 相等，组合 equity/NAV 不出现跳变（允许因手续费/真实价格波动产生差异，但本测试中应为 0）。
- **Paper/Live：拆股公告但券商未更新 → 不应用 + 冻结交易（BUG-CA-01）**：D0 收盘持仓 `shares=10, avg_cost=100`。D1 为 2-for-1 生效日；本地数据源/公告已产生 `split_event(status='announced')`，但券商在 D1 开盘前返回 position snapshot 仍为 `shares=10, avg_cost=100`（尚未应用）。期望：
  - 引擎 **不** 执行 `engine_apply_once`（shares/avg_cost 不变）；
  - 该 symbol 的交易状态变为 `BLOCKED_CA_PENDING`，任何新订单被拒绝并记录原因；
  - 当随后券商 snapshot 更新为 `shares=20, avg_cost=50` 后，系统解除冻结并记录 `apply_mode='broker_authoritative'`。
- **幂等（Paper/Live：券商已调整持仓，不得 double-apply；幂等键用 canonical ratio，BUG-CA-02）**：D0 收盘持仓 `shares=10, avg_cost=100`。D1 为 2-for-1 生效日，券商在 D1 开盘前返回 position snapshot：`shares=20, avg_cost=50`（已调整），并提供 `broker_ca_id`（若无则提供 ratio）。期望：
  - 系统记录 split_event 的幂等键优先使用 `broker_ca_id`；否则使用 `(ratio_num, ratio_den)=(2,1)`（禁止 float）；
  - 重放/重复拉取 snapshot 不会导致产生第二条“应用”记录；
  - 引擎不会将 shares 再改为 40（禁止二次应用）。
- **反向拆股零股现金替代（1-for-5，cash-in-lieu）**：D0 收盘 `price=10`，持仓 `shares=11, avg_cost=10`，无现金；D1 为 1-for-5 生效日（`r=0.2`），未复权价格跳变 `price=50`（仅由拆股导致）。若券商回报为整数 shares + cash-in-lieu，则期望：`shares=2, avg_cost=50`，并出现 `cash_in_lieu = 0.2 * 50 = 10`（或以券商现金流水为准）。D1 估值 `2*50 + 10 = 110` 与 D0 的 `11*10 = 110` 相等，组合 equity/NAV 连续。

### 2.2 存储层（Storage）
- 对象存储：S3/MinIO（原始数据、Parquet、回测结果、模型产物、日志归档）
- 分析库：DuckDB（PoC/MVP 首选）；规模上来再 ClickHouse
- 关系型：Postgres（策略配置/参数/实验记录/订单成交/风控事件/权限）；可选 Timescale

### 2.3 研究环境（Research）
- Notebook + IDE：Jupyter/VSCode notebooks + VSCode/PyCharm
- 因子/特征库：输入数据版本 + 代码版本 + 参数 → 输出因子版本；使用 **as-of join** 防止泄露

### 2.4 回测引擎（Backtesting）
- 向量化回测：快、适合参数扫描（先做）
- 事件驱动回测：更贴近实盘订单生命周期（做日内或复杂订单时再做）
- 必须建模：交易成本、滑点、公司行为（至少拆股/现金分红/退市缺失）；v1 回测净值口径按未复权 OHLC（见 NAV/股息会计口径 v1）
- 输出：净值/回撤/换手/暴露/成交统计；每笔交易可复盘（信号→下单→成交→PnL）

### 2.5 Universe v1（ETF-only，免费数据，日频快照 + 版本化）
- **数据源（v1 推荐）**：
  - 主：Stooq（免费日线，覆盖 ETF/股票）或 Nasdaq Data Link 的免费集合（视可用性）
  - 辅：IBKR 历史数据（若有权限）/其他免费源用于校验
- **过滤规则（v1）**：
  - 资产类型：ETF
  - 排除：**杠杆 ETF / 反向 ETF**（依据名称关键词：`2x/3x/Ultra/Leveraged/Bull/Bear/Inverse/Short`，以及发行方/描述字段；若无元数据，维护一份手工 denylist）
  - 价格：`close >= 5 USD`
  - 流动性：`ADV$ (20D) >= 5,000,000 USD`（20 日均成交额，**用未复权 close * volume 计算**；避免拆股/复权扭曲流动性过滤）
  - 上市时间：`listing_days >= 180`（至少 180 个自然日或 120 个交易日；以数据可用性为准，统一口径）
- **快照与版本**：
  - 每个交易日生成 `universe_snapshot(date, version_hash)`；版本 hash 由（规则参数 + 元数据 denylist + 数据 build id）决定
  - 回测/纸交易/实盘均记录使用的 universe 版本（可追溯与可复现）

**生存者偏差 / 退市/停牌处理 v1（BUG-UNIV-01）**
- 目标：在“免费日线 + 日频执行”约束下做到 **可解释、可复现、可审计**，而不是追求完美点位。
- 符号生命周期（Symbol Lifecycle）：
  - `active`：当日有有效 OHLCV（通过质量校验）且满足过滤
  - `inactive`：不满足过滤（例如价格/流动性跌破阈值）→ **禁止新开仓**，但允许平仓
  - `data_missing`：应有交易日但缺失/异常 OHLCV（或校验失败）→ 当日 **冻结交易**（不对该标的下新单/改单），记录 `data_quality=block`
  - `delisted_or_halted`：连续 N 个交易日无有效数据（v1 默认 N=5，可配置）→ 标记为退市/长期停牌疑似；禁止新开仓；若仍有持仓，进入“人工核查/强制平仓流程”（v1 可先实现为告警 + 停止该标的自动交易）
- 回测口径（v1）：
  - Universe 与数据均按 **as-of 当日快照** 使用；不做“未来已知退市列表”的反向清洗。
  - 当标的在持仓期间出现 `data_missing/delisted_or_halted`：v1 回测不做幻想成交；该标的在缺失期间默认按“最后可用收盘价”估值并触发告警标记（报告里必须展示）。
  - （可选，BUG-UNIV-02）更保守的风控估值：对缺失/疑似停牌标的按 `last_close * haircut`（例如 haircut=0.7，可配置）计入风险报表/触发更早的 Risk-Off；但交易执行仍保持冻结/人工核查，不做虚拟成交。

**BUG-UNIV-01 Acceptance Tests（至少 1 条自动化）**
- **Delist/Data-missing 标记**：构造一个标的在 D0 有数据、D1–D5 缺失数据。期望：Universe/数据层在 D5 结束时将其状态置为 `delisted_or_halted`，并且 OMS 在 D1–D5 期间不对该标的产生任何新订单（只允许记录告警）。


### 2.6 策略框架（Strategy Framework）
- Alpha：因子→打分→阈值/排名
- 组合构建：等权/风险平价/波动率目标/优化器（可后置）
- 再平衡：日/周频或触发式
- 建议接口：
  - `generate_signals(asof_dt) -> target_weights`
  - `rebalance_portfolio(current_positions, target_weights, constraints) -> orders`

### 2.7 风险管理（Risk）

**Drawdown Policy v1（组合级）**
- 指标：用日频净值曲线计算 `peak_to_trough_drawdown`（基于收盘净值）
- 触发：`MaxDD >= 10%`（见 Scope 的硬约束）
- 行为：进入 Risk-Off（禁新开仓、只减仓/平仓）+ 10 个交易日冷却 + 回撤恢复至 <6% 后分阶段恢复
- 记录：每次触发写入 `risk_event`（包含时间、峰值、当前净值、DD、采取动作、恢复条件状态）

**Position Sizing Policy v1（现金账户、ETF-only）**
- 目标：满足“单笔风险 ≤ 0.5% NAV”与“单持仓 ≤ 20% NAV”双约束
- 止损模型（v1 必须二选一并固化在回测/纸交易/实盘中）：
  1) **ATR 止损**：`stop_distance = ATR(14) * 2.0`（可配置 n，v1 默认 2）
  2) **固定百分比止损**：`stop_distance = entry_price * 0.05`（5%）
- 仓位计算（示例，按 ATR 止损）：
  - `risk_budget = 0.005 * NAV`（0.5%）
  - `shares_by_risk = floor(risk_budget / stop_distance)`
  - `shares_by_cap = floor((0.20 * NAV) / entry_price)`
  - `shares = min(shares_by_risk, shares_by_cap, shares_by_cash)`（现金约束：`shares_by_cash` 必须只基于 `available_cash`/`settled_cash` 计算，见 Cash Settlement Policy v1）
- 出场/止损执行（v1 简化）：
  - 仅用**日线**评估止损：若当日 `low <= stop_price`，则次日按 Execution Assumptions v1 执行卖出（避免假设可在日内精确成交）
  - 可选：时间止损（例如持有超过 N 天仍未盈利则减仓），后续版本再加

### 2.8 执行层（Execution）
- 券商 API：IBKR 或 Alpaca（先选一个）
- OMS：订单生命周期状态机（New/Submitted/PartiallyFilled/Filled/Cancelled/Rejected）
- 关键：幂等（避免重复下单）、断线重连后对账恢复

**Execution Assumptions v1（EOD 信号 → 次日执行；回测==纸交易）**
- 信号生成时间：每个交易日 **美东 16:10 ET**（收盘后，留 10 分钟给数据落地/校验）
- 下单时间（BUG-EXEC-01，对齐成交价模型）：次日 **美东 09:30 ET（开盘时）** 发送市价单（v1 固定一个时间点，保持确定性）
- 成交价格模型（必须一致）：
   - 价格（BUG-EXEC-02）：回测与纸交易统一按 **`next_open * (1 ± slippage_bps)`**（v1 不依赖分钟数据；买入用 `+`，卖出用 `-`）
  - 成本（固定且全链路一致）：
    - 滑点：`slippage_bps = 5`（0.05%）
    - 佣金：`commission_bps = 0`（默认 0；若券商收费则配置为固定 bps/每股费用并落库）
- 未成交/部分成交处理：
  - 市价单通常可成交；若出现 `Rejected/Unfilled`：
    - 当天不追价，订单取消
    - 该标的在本次 rebalance 视为未建仓，并在日志记录原因
    - 下个交易日如信号仍有效再尝试（避免在同日反复下单）

**OMS 幂等与稳定性验收（Paper Trading Acceptance Tests v1）**
- `rebalance_id`：每次再平衡生成全局唯一 `rebalance_id`（包含策略 id + asof_dt + universe_version_hash + config_hash）
- 幂等下单：同一 `rebalance_id + symbol + side` 只能产生 1 个“有效订单”（重复调用必须返回已存在订单 id）
- 重启恢复：
  - 进程重启后，OMS 先从 DB + broker 拉取 open orders/positions 对账，再继续执行
  - 验收测试：重启 3 次不产生重复订单；订单状态机可恢复到一致状态
- 无重复订单：
  - 验收测试：网络超时/重试场景下（模拟 10 次重试），broker 侧订单数不超过 1

### 2.9 监控告警（Monitoring & Alerting）
- 指标：PnL、回撤、敞口、换手、滑点偏差、数据延迟、拒单率/异常订单
- 告警：邮件/Telegram/Slack 任一
- 自动处置（谨慎）：只减仓/停机/全平（需预案）

### 2.10 日志审计（Logging & Audit）
- 记录：git commit、配置版本、数据版本、universe 版本、参数；每个信号与订单的原因与风控结果
- 目标：任意一天可重放并解释为什么交易、为什么赚/亏

---

## 3) 迭代路线图（交付物 + 阶段门验收标准）

### 0–2 周：PoC（验证闭环）
交付物：
- 日线数据接入 + 价格口径一致性（未复权 OHLC）+（可选）股息数据接入
- 最小回测（向量化优先）输出净值/回撤/交易列表
- 1 个基准策略（例如 ETF 趋势跟随）
- 风控：单笔风险与单标的上限（按 v1 固定参数）
- 一键跑通：拉数据→算因子→回测→报告（可重复）

**PoC Acceptance Criteria（可量化）**
- 可复现：同一 `data_build_id + code_commit + config_hash` 回测两次结果完全一致（净值序列哈希一致）
- 可审计：每笔交易具备 `signal_dt / exec_dt / price_model / universe_version / position_size_reason`
- 策略闭环：至少 3 年日频回测、输出核心指标（年化/波动/MaxDD/换手/成本占比）
- 回测一致性：使用 Execution Assumptions v1 的价格/滑点模型（禁止“回测用 close、纸交易用 open”这种不一致）

### 2–6 周：MVP（可纸交易）
交付物：
- 数据流水线：定时更新、质量校验、数据版本号、双源校验告警
- Universe v1：日频快照 + 版本化（可追溯）
- 策略框架：可挂多策略
- 执行：接 1 家券商纸交易；OMS + 状态机 + 幂等 + 断线恢复
- 监控：PnL、敞口、订单异常、心跳告警
- 审计：运行元数据、订单/成交全链路落库

**MVP Acceptance Criteria（可量化）**
- 稳定性：连续 20 个交易日自动运行（含数据更新、信号、下单、对账、报告），0 次人工介入的“致命失败”（可允许非关键告警）
- 幂等：对同一 `rebalance_id` 重跑 5 次不产生重复订单（broker 侧订单数=1）
- 重启恢复：模拟进程重启（在下单前/下单后/部分成交后）各 1 次，系统可恢复且不重复下单
- 风控一致：触发 MaxDD=10% 时，系统在 T+0 收盘后进入 Risk-Off，T+1 不新增仓位（通过日志/订单证明）

### 6–12 周：Beta（可控上线）
交付物：
- 回测真实性提升：成本/滑点/公司行为更完整
- 风险体系：组合止损、波动率目标、策略级风控与降级
- 可靠性：重试/断点续跑/灾备预案
- 工程化：Docker + CI/CD

**Beta Acceptance Criteria（可量化）**
- 回测/纸交易一致：同一策略在“纸交易回放模式”（用回测价格模型）与真实 paper broker 执行的日频结果偏差可解释且受控：
  - 成交价偏差均值 ≤ 10 bps，P&L 偏差（绝对值）≤ 0.5% NAV / 月（或给出更合适阈值并固定）
- 风控覆盖：实现 Kill Switch（禁新单/撤单/仅减仓/全平），并完成演练 3 次（含断线/拒单/数据异常）
- 可观测：关键指标（PnL/DD/敞口/订单错误率）可视化；告警在 1 分钟内送达

### 上线后运维
- 盘后对账/复盘；每周漂移检查；每月 walk-forward 再验证与成本模型校准

---

## 4) 技术选型建议

### Python 生态
- pandas（生态全）/ Polars（更快）
- numpy/scipy/statsmodels/sklearn（注意时间序列泄露）

### 回测框架对比
- vectorbt：向量化快，适合研究与参数扫描；复杂订单细节较弱
- backtrader：事件驱动，订单模型更贴近实盘；性能一般
- zipline-reloaded：研究范式成熟；环境/数据适配成本较高

### 数据库/存储：何时用哪个
- DuckDB：PoC/MVP 单机分析首选
- Postgres(/Timescale)：元数据、订单成交、审计、监控指标（MVP 起建议上）
- ClickHouse：日内/高维数据、并发分析（规模上来再上）

### 任务调度
- PoC/MVP：cron
- 推荐：Prefect（轻量、重试/可视化好）
- Airflow：更重，适合成熟数据平台团队

### 部署与安全
- Docker + GitHub Actions
- 密钥：.env（不进 git）→ 规模化再 Vault
- 权限隔离：执行容器持有交易 key；研究容器拿不到

---

## 5) QA / 合规与常见坑
- 回测偏差：幸存者偏差、未来函数/lookahead、数据泄露、回测与实盘执行不一致
- 免费数据坑：缺失/延迟/复权口径不一致；必须做双源校验与数据版本化
- 美股特性：熔断/LULD、T+1 结算影响资金可用性；做空借券/融券费率/强平风险（v1 不做空）
- 应急：Kill Switch（禁新单/撤单/仅减仓/全平）；断线恢复先对账再行动；所有自动处置可追溯

---

## 6) 最小可行策略示例：ETF 趋势跟随（日/周频）
- 数据：ETF 日线 OHLCV（未复权，作为成交/估值/NAV 口径）；（可选）股息/公司行为数据
- 信号：快慢均线（如 20/100 或 50/200）；或 6 个月动量排序取前 K 等权
- 再平衡：每周/每月
- 风控：单 ETF 上限；组合回撤阈值降仓/停机；止损模型与仓位按 Position Sizing v1
- 评估：年化/波动/最大回撤/换手/成本占比；参数敏感性与 walk-forward

---

## 需要 Jie 提供的信息清单
1) 优先频率：**日频（已确认）**
2) 券商：IBKR 还是 Alpaca？现金/融资？**现金账户（已确认）**
3) 风险偏好（已确认）：MaxDD=10%；单笔风险=0.5% NAV；单标的上限=20%；不做杠杆
4) Universe（已确认）：只做 ETF（ETF-only），排除杠杆/反向
5) 数据预算（已确认）：先免费数据起步（需要双源校验 + 价格/股息口径一致性）
6) 部署：本机/家用服务器/云？是否需要 7x24 监控
7) 团队规模：1 人还是 2–5 人？是否需要更严格权限/审计
8) 使用场景：仅自用交易 or 对外展示/他人使用（影响审计与合规模块优先级）
