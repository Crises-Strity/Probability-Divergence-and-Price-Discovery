"""
phase0_pair_inventory.py  (v2 — 修正 search 结构 + 字段名 + event/market 嵌套)
"""
import json, re, time, requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from dateutil.relativedelta import relativedelta

GAMMA = "https://gamma-api.polymarket.com"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.1"}


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
OUT_DIR = PROJECT_ROOT / "result" / "P0_data_audit"

# ---------- 1. 抓取: public-search 返回 events, markets 嵌在里面 ----------
def fetch_events(keyword, limit=100, max_pages=20):
    out, page = [], 0
    while page < max_pages:
        r = requests.get(f"{GAMMA}/public-search",
                         params={"q": keyword, "limit_per_type": limit, "page": page},
                         headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        events = data.get("events", [])
        if not events:
            break
        out.extend(events)
        page += 1
        time.sleep(0.3)
        # public-search 可能不支持 page 翻页; 若每次返回相同, 跳出避免死循环
        pg = data.get("pagination", {})
        if not pg.get("hasMore", False):
            break
    return out

def jload(x):
    if isinstance(x, str):
        try: return json.loads(x)
        except Exception: return None
    return x

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

# ---------- 2. 题型分类 ----------
RE_STRIKE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(k|K)?")
def classify(question: str):
    q = question.lower()
    is_btc = any(w in q for w in ["bitcoin", "btc"])
    is_eth = ("ethereum" in q) or re.search(r"\beth\b", q) is not None
    asset = "BTC" if is_btc else ("ETH" if is_eth else None)
    if asset is None:
        return None

    # 排除 5min Up/Down 超短市场
    if "up or down" in q:
        return {"asset": asset, "qtype": "intraday_binary", "strike": None}

    # 路径触碰型: reach/hit/touch/dip to/fall to/drop to/climb to
    touch = any(w in q for w in ["reach", "hit", "touch", "dip to", "fall to",
                                 "drop to", "climb to", "rise to", "anytime", "ever"])
    bucket = ("between" in q) or re.search(r"\$?[\d,]+k?\s*(?:to|-|–)\s*\$?[\d,]+k?", q)
    point = any(w in q for w in ["above", "below", "greater than", "less than",
                                 "be at", "exceed", "close above", "close below"])

    if touch:                       qtype = "touch_barrier"
    elif bucket:                    qtype = "terminal_bucket"   # ★区间, 可重建分布
    elif point:                     qtype = "terminal_point"    # 单阈值
    else:                           qtype = "unknown"

    nums = []
    for m in RE_STRIKE.finditer(question.replace(",", "")):
        v = float(m.group(1))
        if m.group(2): v *= 1000
        if v >= 1000:  nums.append(v)
    # bucket 型抽下界(上界用 max), point/touch 用唯一 strike
    strike = max(nums) if nums else None
    strike_low = min(nums) if nums else None
    return {"asset": asset, "qtype": qtype, "strike": strike, "strike_low": strike_low}

# ---------- 3. Deribit expiry 粗对标 ----------
def last_friday(year, month):
    d = datetime(year, month, 28, tzinfo=timezone.utc) + relativedelta(day=31)
    while d.weekday() != 4:
        d -= relativedelta(days=1)
    return d

def maps_to_deribit(end_dt, tol_days=4):
    if end_dt is None: return False
    return abs((end_dt - last_friday(end_dt.year, end_dt.month)).days) <= tol_days

def parse_dt(s):
    if not s: return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    # ★强制 aware: 缺 tz 就补 UTC, 避免 naive/aware 相减报错
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

import re
def maps_to_deribit_monthly(question, end_dt, tol_days=4):
    if end_dt is None:
        return False
    # ★排除带具体日内时刻的市场 (12AM/4PM/8PM ET / "at ... ET"), 这些对不齐月度期权
    if re.search(r"\d{1,2}\s?(am|pm)\b|at\s+\d|et\?", question.lower()):
        return False
    # 必须 ≈ 月末周五 (Deribit 月度到期)
    return abs((end_dt - last_friday(end_dt.year, end_dt.month)).days) <= tol_days

# ---------- 4. 主流程 ----------
def run():
    events = []
    for q in ["bitcoin", "ethereum", "bitcoin price", "ethereum price"]:
        events += fetch_events(q)
    # event 去重
    seen_e, uniq_events = set(), []
    for e in events:
        eid = e.get("id")
        if eid and eid not in seen_e:
            seen_e.add(eid); uniq_events.append(e)

    rows, seen_m = [], set()
    for e in uniq_events:
        for m in e.get("markets", []):
            mid = m.get("id") or m.get("conditionId")
            if not mid or mid in seen_m: continue
            seen_m.add(mid)
            cls = classify(m.get("question", "") or "")
            if cls is None: continue
            end_dt = parse_dt(m.get("endDateIso") or m.get("endDate"))
            prices = jload(m.get("outcomePrices"))
            rows.append({
                "event":     e.get("title"),
                "question":  m.get("question"),
                "asset":     cls["asset"],
                "qtype":     cls["qtype"],
                "strike":    cls["strike"],
                "endDate":   end_dt,
                "closed":    m.get("closed"),
                "volume":    num(m.get("volumeNum") or m.get("volume")),
                "liquidity": num(m.get("liquidityNum") or m.get("liquidity")),
                "spread":    num(m.get("spread")),
                "bestBid":   m.get("bestBid"),
                "bestAsk":   m.get("bestAsk"),
                "yes_price": (prices[0] if prices else None),
                "deribit_mappable": maps_to_deribit(end_dt),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        print("仍为空——把 fetch_events 第一条 event 的 keys print 出来看结构"); return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "phase0_inventory.csv", index=False, encoding="utf-8-sig")

    print(f"\n=== 总量 ===\ncrypto 价格市场: {len(df)}  (来自 {len(uniq_events)} 个 event)")
    print("\n=== 资产 × 题型 ===")
    print(df.groupby(["asset", "qtype"]).size().unstack(fill_value=0))
    print("\n=== ★命门: 题型占比 ===")
    print((df.qtype.value_counts(normalize=True) * 100).round(1).astype(str) + " %")
    print("\n=== terminal(可直接对标)分层 ===")
    core = df[df.qtype.isin(["terminal_point", "terminal_bucket"]) & df.deribit_mappable]
    print(f"terminal & Deribit-mappable: {len(core)}")
    for thr in [1e3, 1e4, 1e5]:
        print(f"  volume>=${thr:,.0f}: {len(core[core.volume>=thr])}")
    print("\n=== touch_barrier(路径型, 数量也要看)===")
    tb = df[(df.qtype=='touch_barrier') & (df.volume>=1e4)]
    print(f"touch_barrier & volume>=$10k: {len(tb)}")
    print("\n=== 抽样 40 条人工审题型 ===")
    print(df.sample(min(40,len(df)))[["question","qtype","strike","deribit_mappable","volume"]].to_string())

if __name__ == "__main__":
    run()
