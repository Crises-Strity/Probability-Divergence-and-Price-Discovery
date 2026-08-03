# Dissertation Topic Outline

更新时间: 2026-06-30

> P2 freeze decision (2026-08-03): wild cluster bootstrap was not implemented.
> Event-clustered standard errors and p-values are descriptive diagnostics;
> directional price discovery remains unidentified. References below to
> bootstrap as primary inference are retained only as historical planning.

## 1. 暂定题目

主标题候选:

```text
Cross-Market Probability Divergence and Price Discovery between Crypto Prediction Markets and Crypto Options Markets
```

更具体版本:

```text
Probability Divergence and Price Discovery between Polymarket BTC/ETH Price Events and Deribit Crypto Options
```

中文理解:

```text
本文研究 Polymarket 的 BTC/ETH 终值价格事件市场与 Deribit 加密期权市场之间的概率定价差异和价格发现关系。
```

目前先不定死最终标题。等实证结果出来后, 标题可以根据主发现调整:

```text
如果 lead-lag 明显: 强调 price discovery
如果 lead-lag 方向不可识别但 convergence/divergence 清楚: 强调 probability divergence and frequency-bounded integration
如果交易信号不显著: 强调 market efficiency / limits to arbitrage
```

## 2. 一句话研究主线

英文版本:

```text
This dissertation studies cross-market probability divergence and frequency-bounded price discovery between Polymarket terminal BTC/ETH price-event markets and Deribit crypto options, using daily full-distribution comparisons and multi-hour local survival-probability integration tests.
```

中文版本:

```text
本文研究 Polymarket 的 BTC/ETH 终值价格事件市场与 Deribit 加密期权市场之间的概率定价差异和频率受限的价格发现关系; 日频层面比较完整概率分布, 多小时频层面用局部生存概率检验跨市场整合, 并明确方向性 lead-lag 在当前数据下不可识别。
```

## 3. 核心研究问题

### RQ1: Distribution Alignment

问题:

```text
Polymarket event probabilities 与 Deribit risk-neutral probabilities 之间的分布 wedge 有多大、是否稳定、集中在哪些价格区间?
```

更严格表述:

```text
After matching event horizons and controlling for liquidity, settlement references, and probability-measure differences, how large and stable is the wedge between Polymarket event-implied probabilities and Deribit option-implied risk-neutral probabilities?
```

可能结果:

```text
高度一致
存在稳定 wedge
只有部分区间一致
尾部差异最大
controls 后 residual divergence 很小
```

### RQ2: Divergence Dynamics

问题:

```text
两市场的 probability divergence 是否具有结构性, 是否会主动收敛?
```

必须避免:

```text
把 terminal mechanical convergence 误当 active mean reversion。
```

方法上需要:

```text
控制 time-to-expiry
控制 horizon gap 和 settlement/reference mismatch
排除或单独分析临近结算窗口
区分 raw divergence 和 residual divergence
```

### RQ3: Price Discovery / Lead-Lag

问题:

```text
在同一终值价格事件上, Polymarket 和 Deribit 的局部生存概率是否同步整合? 当前流动性约束下能否识别谁先反应?
```

最终方法:

```text
bucket-distribution events only as primary Track B sample
hourly local survival probability P(S_T > K*) as feasibility diagnostic
6h local survival probability as the primary measurable frequency
changes for co-movement tests; levels for convergence checks
stale / non-synchronous trading diagnostics before any directional interpretation
```

而不是:

```text
hourly full RND
relaxed hourly Deribit estimator that adds noisy non-traded observations
```

P1 实证后冻结的结果:

```text
level convergence is strong
6h contemporaneous co-movement is strong
hourly lead-lag is not measurable because Deribit local-survival changes are dominated by microstructure noise
directional lead-lag is unidentified
```

论文主线应写成:

```text
frequency-bounded cross-market integration, not a PM-leads-Deribit story
```

### RQ4: Optional Trading / Economic Value

问题:

```text
probability divergence 是否能转化为相对价值信号?
```

注意:

```text
这不是主承诺。
如果统计 divergence 存在但交易后不显著, 仍然是合格结果。
```

## 4. 初步假设

这些是假设框架, 后面可以根据导师意见调整。

### H1: Cross-Market Probability Relation

```text
Polymarket and Deribit probabilities should be positively related for matched terminal BTC/ETH events.
```

说明:

```text
不假设二者相等, 因为 Polymarket 更接近 event / physical probability, Deribit 是 risk-neutral probability。
```

### H2: Residual Divergence Contains Structure

```text
After controlling for time-to-expiry, liquidity, and structural P-vs-Q wedge, residual divergence may show mean-reverting or persistent patterns.
```

注意:

```text
必须区分 active convergence 和 terminal mechanical convergence。
controlled residual in levels is not identified as mispricing, because latent time-varying risk premia remain.
```

### H3: Price Discovery Is State-Dependent

```text
Lead-lag direction may depend on liquidity, asset, time-to-expiry, and whether information is event-specific or option-market-driven.
```

不要写成简单的:

```text
Polymarket always leads / Deribit always leads
```

### H4: Tradable Value May Be Limited

```text
Even if divergence is statistically visible, it may not survive spreads, stale prices, execution constraints, and hedging costs.
```

Stronger limitation:

```text
Horizon-mismatched Polymarket-Deribit legs cannot be perfectly hedged because binary event payoff and continuous option payoff settle on non-identical structures and sometimes non-identical times.
```

## 5. 数据章节大纲

### 5.1 Data Sources

Polymarket:

```text
Gamma public-search API
CLOB prices-history
```

Deribit:

```text
public option OHLC through get_tradingview_chart_data
```

可能的辅助数据:

```text
BTC/ETH spot or index price
```

目前暂不主线使用:

```text
Kalshi
Bybit
NLP / news / social media
```

### 5.2 Event Universe

保留:

```text
terminal_bucket
terminal_point
```

排除:

```text
touch_barrier
intraday_binary
unknown
```

理由:

```text
touch_barrier 是路径依赖, 不能直接和 vanilla option terminal distribution 对标。
```

### 5.3 Event Matching

匹配标准:

```text
Polymarket settlement time vs nearest Deribit option expiry
```

分档:

```text
exact
close
loose
unmappable
```

主样本:

```text
exact + close
```

robustness:

```text
loose
```

### 5.4 Sample Description

当前 P0 数字:

```text
124 target events
79 clean bucket-distribution events
45 usable point-threshold events
BTC 60 / ETH 64
median event life 6.99 days
```

论文里要强调:

```text
样本不是几万个 market rows, 真正独立研究对象是 event-level trajectories。
79 clean bucket-distribution events 是 Track A 主样本, 也是 Track B 主样本。
45 usable point-threshold events 不进入 P1 Track B 主结果, 因为 saturation 太高, 有效时序方差不足; 只能作为 extension / external-validity slice。
```

## 6. Confirmatory vs Exploratory Discipline

本项目分支很多, 所以必须在正式实证前冻结主规格。否则 BTC/ETH, exact/close, 1h/2h/4h, K* selection, smoothing method 等选择会形成 forking paths。

### 6.1 Primary Specification

Track A primary is split into two specifications:

```text
Spec A1: wedge explanation / RQ1
sample: BTC+ETH pooled, clean bucket-distribution events, exact+close mapping
frequency: daily
Polymarket: complete partition probabilities after warm-up and sum-quality filters
Deribit: daily OHLC-implied bucket probabilities from shape-constrained / smoothed option curve
LHS: event-day distribution distance, or cell-day raw divergence
FE: asset FE; cell/moneyness FE only for cell-day LHS; no event FE
main estimand: observable drivers of P-vs-Q wedge
controls: time-to-expiry, horizon gap, settlement/reference mismatch, mapping quality, liquidity/staleness controls, tail-cell indicator, cross-strike trade-time spread
inference: event-level wild cluster bootstrap as primary; clustered SE as descriptive

Spec A2: within-event residual dynamics / RQ2
sample: same clean bucket-distribution events
frequency: daily
LHS: change in unexplained wedge component / residual divergence proxy
FE: event FE, optional cell/moneyness FE
main estimand: residual dynamics / weak evidence of active adjustment
controls: time-varying controls only
not estimated: horizon gap, settlement/reference mismatch, mapping quality, asset effect
```

Track B primary:

```text
sample: BTC+ETH pooled bucket-distribution events only
frequency: hourly for feasibility diagnostics; 6h for primary measurable integration tests
K*: rule-selected event-start ATM boundary for bucket events
Polymarket: P_PM(S_T > K*) from cell sums
Deribit: P_DER(S_T > K*) from local/ATM option information
main estimand: level convergence and 6h contemporaneous co-movement in survival-probability changes
directional lead-lag: reported as unidentified unless symmetric lead correlations and measurement-error diagnostics support a direction
mandatory diagnostics: update/trade frequency, time since last update/trade, both-sides-real-update subsample, low-stale subsample, initial K* moneyness, K* moneyness drift, survival saturation, frequency coarsening diagnostics
inference: event fixed effects plus event-clustered SE / wild cluster bootstrap where applicable
```

### 6.2 Robustness / Exploratory Specifications

Robustness:

```text
BTC-only vs ETH-only
exact-only vs exact+close
hourly vs 4h vs 6h vs 12h frequency diagnostics
alternative K* rules
alternative Deribit smoothing methods
exclude low-volume events
exclude warm-up and final settlement windows
stale-ratio terciles
both-sides-real-update bars only
tail cells excluded / tail cells separately analyzed
daily curve cross-strike time-spread filters
survival saturation bars excluded or flagged
point-threshold extension only, not pooled into primary Track B
```

Exploratory only:

```text
trading signal / relative value tests
state-space / IV correction for Deribit measurement error
Hasbrouck information share / VECM, future work only with denser quote-level data
state-dependent lead-lag splits beyond the pre-specified controls
```

## 7. 方法章节大纲

### 7.1 Polymarket Probability Reconstruction

Polymarket 事件结构:

```text
left tail + middle buckets + right tail
```

存续期价格:

```text
prices-history YES token price
```

质量控制:

```text
warm-up filter
complete cell coverage
probability sum check
normalization after raw diagnostics
```

### 7.2 Deribit Probability Reconstruction

Deribit 数据现实:

```text
historical order book unavailable
expired mark history unavailable
historical OHLC available
```

Track A:

```text
daily option curve / IV smile -> bucket probabilities
```

Track B:

```text
hourly local ATM survival probability
```

### 7.3 Track A: Distribution Divergence / P-Q Wedge

比较对象:

```text
Polymarket bucket probability
vs
Deribit risk-neutral bucket probability
```

解释纪律:

```text
raw divergence = P-vs-Q / market wedge, not direct mispricing
residual divergence = unexplained wedge component after observable controls
residual levels = unmodeled time-varying risk premium + possible cross-market divergence, not separately identified
residual dynamics = weak evidence channel for active adjustment
convergence tests = must separate active adjustment from terminal mechanical convergence
```

方程纪律:

```text
Spec A1 estimates event-level / event-day wedge drivers and therefore cannot include event fixed effects.
Spec A2 estimates within-event residual dynamics and therefore can include event fixed effects, but cannot estimate event-invariant covariates such as horizon gap, settlement mismatch, mapping quality, or asset.
```

指标候选:

```text
L1 distance
L2 distance
largest bucket divergence
tail divergence
location / spread / skew proxy
```

不确定部分:

```text
Deribit smoothing method TBD: SVI / spline / constrained call curve
```

### 7.4 Track B: Price Discovery

核心变量:

```text
P_PM(S_T > K*)
P_DER(S_T > K*)
```

K* 选择:

```text
Bucket events: event-start nearest ATM Polymarket boundary strike.
Point-threshold events: market-defined threshold, extension only.
```

K* source discipline:

```text
Primary Track B uses rule_selected K* from bucket-distribution events only.
K_star_source must still be recorded for extension samples.
Initial K* moneyness must be reported because extreme initial survival creates saturation and weakens lead-lag identification.
Point-threshold events are not pooled into the main Track B sample.
```

Point-threshold quality gate:

```text
minimum Polymarket volume / liquidity
minimum real update frequency
maximum stale share
survival probability not saturated outside [0.05, 0.95] for most of event life
Deribit local strike coverage around market-defined K*
```

测试方法:

```text
update/trade frequency diagnostics first
both-sides-real-update robustness
full sample vs both-sides-real-update comparison as measurement sensitivity
point-threshold extension only
initial moneyness controls
K* moneyness drift and survival saturation diagnostics
cross-correlation by lag
pooled lead-lag regression on probability changes, interpreted with measurement-error caveat
event fixed effects
wild cluster bootstrap inference
```

不确定部分:

```text
P1 不使用 VECM / Hasbrouck information share。原因是每事件连续 run 和 Deribit local-survival measurement error 不支持 per-event price-discovery decomposition。
```

### 7.5 Optional Trading Signal

如果加入:

```text
signal predictability first
tradability second
```

不能写:

```text
risk-free arbitrage
```

应写:

```text
relative value signal
```

## 8. 论文章节结构

### Chapter 1: Introduction

内容:

```text
研究背景
为什么 prediction market 和 crypto options 可以同时定价终值事件
为什么二者可能有 P-vs-Q wedge 和 residual divergence
研究问题和贡献
```

贡献初稿:

```text
1. 构建 Polymarket-Deribit terminal event matching framework
2. 测量 prediction-market event probabilities 与 option-implied risk-neutral probabilities 的 P-vs-Q wedge
3. 用双轨方法区分 daily distribution wedge/residual divergence 和 intraday price discovery
4. 显式处理 stale prices, non-synchronous trading, terminal convergence 和 probability-measure mismatch
```

### Chapter 2: Literature Review

板块:

```text
Prediction markets and information aggregation
Option-implied risk-neutral distributions
Price discovery and lead-lag across markets
Crypto derivatives and market microstructure
```

暂不确定:

```text
具体文献待系统检索后补。
```

### Chapter 3: Data

内容:

```text
Polymarket data
Deribit data
event matching
sample construction
data quality and feasibility
```

重点:

```text
event life ~7 days
complete partition structure
Deribit historical OHLC rather than order book
10,842 no-intraday terminal candidates 的漏斗解释
```

### Chapter 4: Methodology

内容:

```text
Polymarket probability reconstruction
Deribit option-implied probability reconstruction
Track A daily distribution divergence
Track B local survival probability convergence and frequency-bounded lead-lag diagnostics
confirmatory vs exploratory specification table
econometric tests
optional trading signal design
```

### Chapter 5: Empirical Results

建议顺序:

```text
5.1 Data coverage and quality
5.2 Example event distribution comparison
5.3 Full-sample daily P-vs-Q wedge and residual divergence
5.4 Divergence dynamics / active vs terminal convergence
5.5 Track B local survival-probability convergence
5.6 Frequency-bounded lead-lag diagnostics
5.7 Stale / non-synchronous trading, K* moneyness, and saturation diagnostics
5.8 Optional trading signal
```

P1 冻结后的结果口径:

```text
Track A: center aligned, tail-relative divergence material, spread wedge smoothing-conditional, L1 shape distance secondary.
Track B: level convergence and 6h contemporaneous co-movement are supported; directional lead-lag is unidentified.
```

### Chapter 6: Robustness and Discussion

内容:

```text
BTC vs ETH
exact vs exact+close
hourly vs 4h vs 6h vs 12h frequency diagnostics
alternative K*
alternative Deribit smoothing
exclude warm-up / final settlement window
liquidity filters
```

必须讨论:

```text
P vs Q wedge
terminal convergence vs active convergence
stale price and last-trade noise
daily curve cross-strike non-simultaneity
non-synchronous trading artifact
favorite-longshot bias in Polymarket tails
small event-cluster inference and wild cluster bootstrap
limits to tradability
horizon-mismatched hedge and binary-vs-continuous payoff mismatch
```

### Chapter 7: Limitations and Conclusion

限制:

```text
sample is template-like BTC/ETH terminal price events
events live around 7 days
Deribit uses OHLC not historical order book
Polymarket and Deribit probabilities are not the same measure
Deribit local-survival changes are noisy at hourly frequency
6h aggregation makes co-movement measurable but cannot identify sub-6h price discovery
trading signal, if any, is not arbitrage
```

结论待定:

```text
no robust directional lead-lag in P1; frequency-bounded integration is the defensible conclusion
```

## 9. 当前待定内容清单

这些后续慢慢推进:

```text
final title
final wording for Track B result section
whether point-threshold extension is worth reporting outside limitations
whether trading signal becomes a full chapter
final primary specification after supervisor feedback
```

## 10. 面试 30 秒版本

当前版本:

```text
I study whether Polymarket and Deribit agree on the probability distribution of the same BTC/ETH terminal price events. I first match Polymarket event partitions to Deribit option expiries, reconstruct Polymarket event probabilities from CLOB price history, and infer Deribit risk-neutral bucket probabilities from historical option OHLC. The empirical design has two tracks: daily full-distribution divergence, and multi-hour local survival-probability integration around an ex-ante ATM threshold. The main risks are horizon mismatch, physical-vs-risk-neutral probability wedges, stale option trades, and measurement-error-driven lead-lag artifacts, so the project focuses on data quality filters and robustness rather than claiming mechanical arbitrage or one-sided market leadership.
```

中文口语版:

```text
我比较 Polymarket 和 Deribit 对同一 BTC/ETH 终值价格事件的概率定价。Polymarket 给的是事件市场概率, Deribit 期权反推出的是风险中性概率。日频层面我比较完整分布, 多小时频层面我用 ATM 附近的 survival probability 看两个市场是否同步整合。当前结果支持 level convergence 和 6h 同期共动, 但不支持把方向写成谁领先谁。这个项目的重点不是硬挖套利, 而是严谨处理事件匹配、概率口径差异、流动性和 stale price 后, 检验两个市场之间是否有稳定 divergence 和频率受限的信息整合。
```
