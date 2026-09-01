# -*- coding: utf-8 -*-
"""
probe_gsb.py - 规则库命中率摸底（§3.4 校准的第一份基线数据）

用一批代表性回应跑一遍 GSB + RSB，统计：
- 各维度（7 正向 + 2 负向）命中率
- 暴击率 / 红线率 / 分数分布
- 分「优秀/良好/普通/顶撞/空洞/红线」类目的均分

这是未来校准 §3.4 判定参数（暴击线 85、涨落 delta、deadlock 线等）的数据依据。
当前语料是开发期手工构造的代表性样本，真实游玩数据落库后应替换为重跑。
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from collections import Counter, defaultdict

from strategy_kb import StrategyKB
from judge_agent import JudgeAgent
from scenario_store import ScenarioStore
from contracts import is_crit


# 代表性语料（类别, 回应文本）。故意覆盖 优秀/良好/普通/顶撞/空洞/三类红线。
CORPUS = [
    ("优秀", "我理解你，但我不接受这种说法，请停止。我会保持距离，按规则处理，保留记录，并求助物业工作人员。"),
    ("优秀", "请停止，我不接受。我会保持冷静，按事实沟通，并保留记录向物业反映。"),
    ("良好", "我理解你有需求，但请按规则处理，我会记录并联系物业。"),
    ("良好", "请你冷静一点，我们按事实说，不升级冲突。"),
    ("普通", "我理解你，但请按规则处理。"),
    ("普通", "知道了。"),
    ("普通", "这样不对，请停止。"),
    ("顶撞", "都怪你，你必须负责！"),
    ("空洞", "算了，随便吧。"),
    ("空洞", "没事，都行。"),
    ("红线-辱骂", "你滚吧，废物！"),
    ("红线-暴力", "我打你，弄死你！"),
    ("红线-违法", "我要曝光你身份证，人肉你！"),
]


def main():
    kb = StrategyKB()
    judge = JudgeAgent()
    scenario = ScenarioStore().get_scenario("neighbor-noise")

    pos_dims = kb.get_dimensions()["positive"]   # [{id,name,weight}]
    neg_dims = kb.get_dimensions()["negative"]

    # 统计容器
    pos_hits = Counter()          # 正向维度 id -> 命中次数
    neg_hits = Counter()          # 负向维度 id -> 命中次数
    red_line_counts = Counter()   # 红线 id -> 命中次数
    scores_by_cat = defaultdict(list)
    n_crit = 0
    n_red = 0

    print("=" * 60)
    print("逐条回应（类别 | 总分 | 红线 | 命中维度）")
    print("=" * 60)
    for cat, text in CORPUS:
        # 红线检测（RSB）
        red = kb.detect_red_line(text)
        # 维度命中（GSB，正向 + 负向）
        hits, penalties = kb.match_dimensions(text)
        # 权威评分（含红线一票否决）
        result = judge.judge(scenario, "adult", [], text)

        for d in hits:
            pos_hits[d["id"]] += 1
        for d in penalties:
            neg_hits[d["id"]] += 1
        if red is not None:
            red_line_counts[red["id"]] += 1
            n_red += 1
        if is_crit(result.total_score, result.red_line_hits):
            n_crit += 1
        scores_by_cat[cat].append(result.total_score)

        hit_names = [d["name"] for d in hits] + ["-" + d["name"] for d in penalties]
        red_tag = f"红线[{red['id']}]" if red else "—"
        print(f"  [{cat}] 总分={result.total_score:>3} 暴击={'Y' if is_crit(result.total_score, result.red_line_hits) else 'N'} "
              f"红线={red_tag} 命中={hit_names}")

    total = len(CORPUS)
    print()
    print("=" * 60)
    print(f"汇总（语料 N={total}）")
    print("=" * 60)

    # 暴击率 / 红线率
    print(f"暴击率：{n_crit}/{total} = {n_crit / total:.0%}")
    print(f"红线率：{n_red}/{total} = {n_red / total:.0%}")

    # 正向维度命中率
    print("\n正向维度命中率（命中次数 / 语料总数）：")
    for d in pos_dims:
        c = pos_hits.get(d["id"], 0)
        print(f"  {d['name']:<8} 权重 {d['weight']:>2}  ->  {c:>2}/{total} = {c / total:.0%}")

    # 负向维度命中率
    print("负向维度命中率：")
    for d in neg_dims:
        c = neg_hits.get(d["id"], 0)
        print(f"  {d['name']:<8} 权重 {d['weight']:>3}  ->  {c:>2}/{total} = {c / total:.0%}")

    # 红线命中分布
    print("\n红线命中分布：")
    for r in kb.get_red_lines():
        c = red_line_counts.get(r["id"], 0)
        print(f"  {r['id']:<12} ->  {c} 次")

    # 分门类均分
    print("\n分门类均分：")
    order = ["优秀", "良好", "普通", "顶撞", "空洞", "红线-辱骂", "红线-暴力", "红线-违法"]
    for cat in order:
        vals = scores_by_cat.get(cat, [])
        if vals:
            avg = sum(vals) / len(vals)
            print(f"  {cat:<10} 均分={avg:>5.1f}  样本={vals}")

    print()
    print("提示：本数据反映的是「关键词子串匹配」这一朴素规则的命中分布，")
    print("是校准 §3.4（暴击线 85 是否过高、维度权重是否合理）的起点，非最终结论。")


if __name__ == "__main__":
    main()
