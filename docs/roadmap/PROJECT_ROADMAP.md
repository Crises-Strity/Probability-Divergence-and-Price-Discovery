# Project Roadmap: Probability Divergence and Price Discovery

更新时间: 2026-06-30

## 1. 项目定位

本项目研究 Polymarket 和 Deribit 对同一类 BTC/ETH 终值价格事件的概率定价差异与价格发现关系。

命名纪律:

```text
"Order Book Divergence Signal" 只作为公司给定题目的原始名称。
P0 已确认 Deribit 历史 order book 不可用, 所以后续论文和代码文档使用 Probability Divergence / Price Discovery 作为准确定位。
```

一句话版本:

```text
比较 Polymarket terminal price-event probabilities 与 Deribit option-implied risk-neutral probabilities, 并检验两者的 divergence、cross-market integration 和频率受限的 lead-lag 可识别性。
```

P1 empirical freeze update:

```text
Track A 已完成: PM 与 Deribit 在 distribution center 上基本一致; tail-relative divergence 仍然明显; spread wedge 在 low-to-moderate smoothing 下为正, 但 heavy smoothing 下衰减, 所以必须写成 smoothing-conditional; L1/L2 shape distance 作为 secondary。
Track B 已完成: bucket-distribution events 是主样本; point-threshold events 因 saturation 太高不进入主结果。hourly Deribit local-survival changes 被 microstructure noise 淹没, 6h 下 level convergence 和 contemporaneous co-movement 成立, 但 directional lead-lag 不可识别。
```

当前项目不是纯套利项目, 也不是简单回测项目。更准确的定位是:

```text
cross-market probability divergence and price discovery study
```

可选延伸才是:

```text
relative value signal / trading signal evaluation
```

## 2. 最终锁定的双轨设计

经过 P0 spike 后, 项目不再采用“小时频 full RND 对比”的原始路线。最终设计分成两条轨:

### Track A: Distribution Divergence

用途:

```text
研究 Polymarket event probability 与 Deribit risk-neutral probability 的完整分布差异。
raw divergence 首先解释为 P-vs-Q / market wedge, 不是直接解释为 mispricing。
controls 后的 residual 仍然混有 latent time-varying risk premium, 不能在 levels 上直接解释为错价。
```

频率:

```text
daily
```

Polymarket:

```text
left tail + middle buckets + right tail
```

Deribit:

```text
daily option OHLC -> smoothed option curve / IV smile -> bucket probabilities
```

主要输出:

```text
bucket-level divergence
distribution distance
tail / location / spread / skew difference
structural wedge size and stability
unexplained wedge component
residual dynamics / convergence test
```

Track A 主规格必须拆成两个:

```text
Spec A1: wedge explanation / RQ1
    LHS = event-day distribution distance or cell-day raw divergence
    FE = asset FE; cell/moneyness FE only for cell-day LHS; no event FE
    可以估 = time-to-expiry, horizon gap, settlement/reference mismatch, mapping quality,
             liquidity / spread / volume, curve quality, tail-cell indicator

Spec A2: within-event residual dynamics / RQ2
    LHS = change in unexplained wedge component / residual divergence proxy
    FE = event FE, optional cell/moneyness FE
    只估 time-varying controls
    不估 horizon gap / settlement mismatch / mapping quality / asset effect
```

原因: horizon gap, settlement mismatch, mapping quality, asset 都是 event-invariant; 一旦上 event FE, 这些变量会被机械吸收, 系数不可估。

### Track B: Price Discovery / Lead-Lag

用途:

```text
研究 Polymarket 与 Deribit 是否在局部生存概率上同步整合, 以及当前数据频率能否识别谁先反应。
```

频率:

```text
hourly feasibility diagnostic
6h primary measurable integration test
4h / 12h frequency diagnostics
```

Polymarket:

```text
P_PM(S_T > K*) = sum of cells above K*
```

Deribit:

```text
P_DER(S_T > K*) from local / ATM option information
```

K* 来源:

```text
bucket-distribution events: K* 由 event-start 最近 ATM boundary 规则选择, K_star_source = rule_selected
point-threshold events: K* 是市场自带 threshold, K_star_source = market_defined, but extension only
```

P1 实证后, point-threshold events 不进入 Track B 主结果。原因不是 K* 定义, 而是 saturation 太高, 有效时序方差不足。主结果使用 bucket-distribution events only; point-threshold 只作为 extension / limitations。

为什么不用小时频 full RND:

```text
小时频 full RND 依赖 tail strikes, last-trade OHLC 噪声大, 会污染 lead-lag / information share。
```

所以 lead-lag 只追一个局部 survival probability, 而不是整条分布。

必须防住的假阳性:

```text
Deribit 使用 last-trade OHLC, Polymarket 使用 CLOB history。
如果一边成交/更新更频繁, lead-lag 可能只是 non-synchronous trading artifact。
P1 必须报告两边真实更新频率, 并在 both-sides-real-update bars / low-stale subsample 中重跑主结果。
hourly lead-lag 如果被 Deribit measurement error 淹没, 不能用 relaxed estimator 硬凑方向; 6h 同期共动可以作为 integration 结果, directional leadership 只能写 unidentified。
```

## 3. P0 已完成内容

P0 目标是验证项目数据可行性, 不追求全量生产数据。

### 3.1 Polymarket Inventory

脚本:

```text
scripts/P0_data_collection/build_polymarket_inventory.py
```

主要输出:

```text
data/raw/polymarket/polymarket_public_search_events.json
data/raw/polymarket/polymarket_market_inventory.csv
data/processed/polymarket/market_pair_candidate_inventory.csv
data/processed/polymarket/event_distribution_quality.csv
```

关键数字:

```text
raw events: 3,758
raw market rows: 22,801
terminal candidates after no-intraday filter: 10,842
event quality rows: 1,040
```

漏斗数字解释:

```text
terminal_bucket + terminal_point = 15,251
其中带 intraday time wording 的 terminal rows = 4,409
  terminal_bucket = 2,769
  terminal_point = 1,640
no-intraday terminal candidates = 15,251 - 4,409 = 10,842
```

4,409 来自 `data/raw/polymarket/polymarket_market_inventory.csv` 的实际分组计数, 不是为了平账反推。 所以 10,842 是 terminal 市场在剔除日内时刻口径后的数量, 不是 terminal_bucket + terminal_point 的直接相加。

可用主样本:

```text
target events: 124
clean bucket-distribution events: 79
usable point-threshold events: 45
BTC events: 60
ETH events: 64
```

Track 使用边界:

```text
79 clean bucket-distribution events 是 Track A 主样本。
79 clean bucket-distribution events 也是 Track B 主样本。
45 usable point-threshold events 不进 Track A, 也不进 P1 Track B 主结果; 只能作为 extension, 因为 saturation 太高且有效时序方差不足。
```

重要结论:

```text
Polymarket terminal_bucket + terminal_point 结构足够支持项目。
touch_barrier 是路径依赖事件, 不进主线。
clean bucket-distribution events 具有完整价格轴剖分。
```

### 3.2 Event Life Check

关键发现:

```text
median event life: 6.99 days
120 / 124 events are in the 3-7 day range
no event has 14/30 day life
```

影响:

```text
日频只适合 Track A 的分布对比。
Track B 的 lead-lag 必须使用 hourly / multi-hour 数据。
```

### 3.3 Polymarket Prices-History Spike

脚本:

```text
scripts/P0_data_collection/polymarket_event_history_spike.py
```

测试事件:

```text
event_id: 21348
event: Bitcoin price on March 28?
```

结果:

```text
history rows: 1,204
hourly distribution rows: 172
all hourly rows in [0.9, 1.1]: 171 / 172
excluding first warm-up row: 171 / 171
```

结论:

```text
Polymarket in-life distribution reconstruction 可行。
必须剔除 event 上线后的 warm-up 1-3 小时。
```

### 3.4 Deribit Availability Check

脚本:

```text
scripts/P0_data_collection/check_deribit_availability.py
```

结论:

```text
historical order book: 不可用
historical mark history: 对 expired options 不可用
historical option OHLC via get_tradingview_chart_data: 可用
```

关键数字:

```text
chart history probes: 156
successful chart histories: 145
success rate: 92.9%
BTC: 77 / 84 = 91.7%
ETH: 68 / 72 = 94.4%
```

影响:

```text
Deribit 侧不能写成 historical order book reconstruction。
Deribit 侧应写成 option-OHLC-implied probability reconstruction。
```

### 3.5 Deribit Grid Spike

脚本:

```text
scripts/P0_data_collection/deribit_single_expiry_grid_spike.py
```

测试事件:

```text
event_id: 21348
Deribit expiry: 2025-03-28 08:00 UTC
strike grid: 66k to 100k, step 2k
```

日频结果:

```text
days with >=6 distinct traded strikes: 30 / 31
days with >=8 distinct traded strikes: 30 / 31
median distinct traded strikes/day: 15
```

小时频结果, 只看 Polymarket event life window:

```text
window: 2025-03-21 16:00 UTC to 2025-03-28 08:00 UTC
bars: 161
>=6 distinct traded strikes: 136 / 161 = 84.5%
>=8 distinct traded strikes: 105 / 161 = 65.2%
median distinct traded strikes/hour: 9
```

结论:

```text
Deribit daily full-grid reconstruction 可行。
Deribit hourly full-RND 有噪声风险, 不应作为 lead-lag 主输入。
Deribit hourly local / ATM survival probability 是更稳的 lead-lag 输入。
Deribit daily curve 还必须控制 cross-strike 成交时间不同步, 不能只看 staleness。
```

## 4. 当前数据可行性结论

已确认:

```text
Polymarket event universe 可构造
Polymarket in-life prices-history 可用
Polymarket complete partition 可重建
Deribit historical option OHLC 可用
Deribit daily full-distribution reconstruction 可行
Deribit local survival probability route 可行, 但 hourly change 信号不可测; 6h 后可测 contemporaneous co-movement
```

已放弃:

```text
historical Deribit order book
historical expired-option mark history
hourly full-RND as main lead-lag input
```

仍需 P1 全量验证:

```text
P1 全量验证已完成并冻结在 docs/decision_logs/P1_EMPIRICAL_FREEZE.md。
剩余工作不是继续调 P1 结果, 而是把 Track A / Track B 的主发现、robustness 和 limitations 写进论文。
```

## 5. P1 要做什么

P1 目标:

```text
把 P0 spike 转成可复现的全量数据管线和第一版 empirical panels。
```

### 5.1 P1 数据管线

需要生成:

```text
data/processed/polymarket/event_cells.parquet
data/processed/polymarket/polymarket_distribution_hourly.parquet
data/processed/polymarket/polymarket_distribution_daily.parquet

data/raw/deribit/ohlc_<event_id>_<resolution>.parquet
data/processed/deribit/deribit_bar_quality.parquet

data/processed/panels/daily_distribution_comparison.parquet
data/processed/panels/lead_lag_survival_panel.parquet
```

### 5.2 P1 第一批诊断

必须先出诊断, 不直接上回归:

```text
Polymarket probability sum quality
Polymarket warm-up filter effect
Deribit daily strike coverage
Deribit hourly local ATM coverage
K* selection distribution
K_star_source distribution
initial K* moneyness by event type
K* moneyness drift / saturated survival bar share
point-threshold substitute quality gate pass rate
Polymarket update frequency vs Deribit trade frequency
stale bar share / time since last trade
Deribit daily cross-strike trade-time spread
Track A daily divergence summary
Track B survival series coverage
```

### 5.3 P1 第一批图

建议先做:

```text
fig_data_event_life_distribution.pdf
fig_p0_polymarket_distribution_example.pdf
fig_p0_deribit_grid_quality_example.pdf
fig_trackA_distribution_comparison_example.pdf
fig_trackB_survival_series_example.pdf
```

## 6. P2 / P3 后续任务

### P2: Empirical Analysis

Track A:

```text
daily distribution divergence
event-level distribution distance
active convergence vs terminal convergence
P vs Q structural wedge measurement
unexplained wedge component after controls
residual dynamics as weak evidence of active divergence
```

Track B:

```text
1h local survival feasibility diagnostic
6h survival probability level convergence and contemporaneous change co-movement
pooled lead-lag regression on changes, interpreted with measurement-error caveat
event fixed effects / event-clustered inference where applicable
both-sides-informative and low-stale diagnostics
bucket-distribution events only as primary sample
point-threshold extension only
```

### P3: Robustness

可能的 robustness:

```text
BTC-only vs ETH-only
exact only vs exact+close
hourly vs 4h vs 6h vs 12h frequency diagnostics
different K* rules
exclude low-volume events
exclude first 1-3 hours
exclude final hours before settlement
alternative Deribit smoothing methods
stale ratio terciles
both-sides-real-update bars only
tail cells excluded / tail cells separately analyzed
K* saturated bars excluded or flagged
market_defined K* vs rule_selected K* split
daily curve cross-strike time-spread filters
```

### P4: Optional Trading Signal

只有在 Track A / Track B 诊断有足够信号后才做。

定位:

```text
relative value signal
```

不要写成:

```text
arbitrage
```

需要扣除:

```text
Polymarket spread
depth / liquidity
execution timing
Deribit hedge cost if hedged
horizon-gap unhedged exposure
binary Polymarket payoff vs continuous option payoff
```

RQ4 先按限制记账, 不提前承诺可交易性。Polymarket 和 Deribit 结算时点不完全一致时, 两腿持有到各自结算会暴露在 gap-period risk 下; 二元 payoff 和 option 连续 payoff 也不是天然一一对冲。即使统计 signal 存在, economic value 也可能被这种结构性不可完全对冲限制, 不只是被交易成本吃掉。

## 7. 论文和项目的关系

代码项目先服务于三件事:

```text
1. 证明样本构造严谨
2. 证明两个市场概率可比但不等价
3. 检验 divergence / lead-lag 是否存在
```

如果最后交易信号不显著, 项目仍然成立:

```text
It is a valid null result if cross-market probability divergence exists statistically but does not survive liquidity, noise, or transaction-cost constraints.
```

## 8. 当前不确定项

这些内容现在先不定死:

```text
最终 title
Track B final wording: integration / frequency-bounded price discovery, not directional leadership
Deribit smoothing method: SVI / spline / constrained call curve
是否加入 trading signal chapter
是否报告 point-threshold extension
是否加入 P2 / trading signal chapter
```

处理方式:

```text
先在 P1 输出 coverage 和 quality diagnostics, 再决定主结果和 robustness 的边界。
```

## 9. 当前建议执行顺序

近期不要继续扩散题目。建议顺序:

```text
1. 锁定 thesis research questions
2. 冻结 primary specification vs robustness 表
3. 建 P1 canonical event/cell table
4. 拉全量 Polymarket prices-history
5. 拉全量 Deribit daily OHLC
6. 做 Track A example + diagnostics
7. 再做 Deribit hourly OHLC 和 Track B panel
8. 先跑 stale / non-synchronous trading diagnostics
9. 最后才考虑 trading signal
```
