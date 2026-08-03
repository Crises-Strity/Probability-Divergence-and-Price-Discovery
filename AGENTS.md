# Project Context

UCL MSc FinTech Dissertation. Topic combines 3 sub-projects:

1. NLP signal extraction: 从 crypto 相关文本 (news / 社媒 / research) 提取信号
2. Trading signals for crypto: 基于 TA + FA + NLP 构造交易信号
3. Crypto risk metrics: 量化 crypto 市场风险

Final deliverable: code repo + dissertation (~10-15k words, LaTeX).
Supervisor 关注点 (assumed, 等我确认): rigor > novelty, ablation > complexity.

---

# Critical Pitfalls (主动监控)

## NLP 部分

- 数据合规: Twitter / Reddit / Telegram 抓取需符合 UCL ethics + 各平台 ToS。
  如果我让你写 scraper, 先警告我合规风险。
- 预训练数据泄漏: 用 BERT / FinBERT / GPT-emb 时, 模型本身见过未来文本。
  - 强制要求按时间切分: 训练用 t < T 的文本, 测试用 t >= T 的文本。
  - 在 ablation 里加一个 "用同时期 random embedding" 对照组。
- Label leakage: 用未来 return 标注情绪 -> 训练集泄漏。必须用 t 时刻文本预测 t+k 时刻 return。
- 多语言: Crypto 推特中英文混杂, 分词器要明确选择。

## Trading Signal 部分

- 数据源:
  - Binance API: 注意历史 K 线 silent revision, 建议本地存档原始数据。
  - CoinGecko: 有 survivorship bias, delisted 币消失。
  - 不要用 Yahoo Finance 的 crypto 数据 (质量差)。
- 交易成本: Crypto 现货 ~10bp, 永续合约 ~5bp + funding。strategy 必须扣成本。
- Look-ahead 高发点:
  - 用 close 价格生成信号又用 close 价格成交 -> 必须 t-1 信号, t open 成交。
  - Resample 时未正确处理 timezone (UTC vs 本地)。
  - Rolling 计算时用了 center=True。
- 回测框架: 简单题目优先用自己写的 vectorized backtest, 不要无脑上 zipline / backtrader。

## Risk Metric 部分

- Crypto vol 的特殊性: fat tail, jump, 7x24 交易 (没有 close-to-open gap)。
- 标准 VaR / ES 用在 crypto 上不充分: 必须加 EVT 或 Hawkes 之类的尾部建模。
- Liquidity risk 不能忽视: 小市值币的滑点比波动率更重要。
- 传染性: 2022 LUNA / FTX 事件说明跨币种相关性骤变 -> DCC-GARCH 或 copula 是加分项。

---

# Workflow Coordination (Codex vs Claude)

我会同时用 Claude 桌面端。分工:

- Codex 主战场: 数据 pipeline / 回测 / 实证结果 / repo 结构 / 论文事实核查。
- Claude 主战场: 论文长文撰写 / 数学推导排版 / 复杂代码 review。

当我说 "review Claude 的输出" 时:

1. 只验证可验证的事实 (代码是否能跑、数字是否一致、引用是否真实)。
2. 不要为了显得有用而挑风格 / 措辞的刺。
3. 如果 Claude 的代码和我 repo 里的事实冲突 -> 以 repo 为准。

---

# Repo Structure (期望)

    .
    ├── data/              # raw (gitignore) + processed
    ├── src/
    │   ├── nlp/           # text pipeline, embedding, signal
    │   ├── signals/       # TA, FA, combined alpha
    │   ├── risk/          # VaR, ES, regime, tail
    │   └── backtest/      # vectorized engine, metrics
    ├── notebooks/         # EDA + final results
    ├── tests/             # pytest, 至少覆盖 backtest 和 label 生成
    ├── paper/             # LaTeX
    └── AGENTS.md

---

# Output Conventions

- 所有回测结果保存为 parquet + 一个 metadata.json (含 git commit hash + 数据 snapshot 日期)。
- 图表统一存 paper/figures/, 命名: fig_<chapter>_<topic>.pdf。
- 表格用 pandas.to_latex() 直接生成, 存 paper/tables/。

---

# Dissertation Section Mapping

当我说 "为 X 章生成结果" 时, 对照:

- Ch3 Methodology -> src/ 里的核心函数 + 数学公式。
- Ch4 Data -> data/ 的 EDA + 数据质量检查。
- Ch5 Results -> notebooks/results_*.ipynb 的最终图表。
- Ch6 Discussion -> ablation + robustness check (rolling window, subperiod, alt benchmark)。
- Ch7 Limitations -> 必须诚实列出, 包括但不限于上面的 pitfalls。

---

# Interview-ability Check

最终每个组件都要能在面试里 30 秒讲清:

- 问题是什么
- 数据是什么 (规模 + 来源 + 质量问题)
- 方法是什么 + 为什么选这个 (vs 备选)
- 结果是什么 (诚实的数字)
- 风险控制 / robustness
- Limitation

如果某个模块讲不清, 说明做得太复杂或太草率, 提醒我简化。
