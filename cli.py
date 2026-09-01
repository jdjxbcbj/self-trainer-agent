# -*- coding: utf-8 -*-
"""
cli.py - 命令行入口（安全对线训练场）

提供交互式命令行，用于在没有前端的情况下手动测试完整训练闭环。
一条用户输入 → 完整回合（评分 + NPC 回应 + 实时提示 + 阶段判定 + 落库）。
终局（通关/失控/到时）自动触发复盘并落库。
"""

import sys
from datetime import datetime

# Windows 控制台默认用 GBK 编码，直接打印/读取中文会乱码；
# 这里在入口处强制 stdin / stdout 都使用 UTF-8，保证中文正常显示与输入。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

from contracts import Audience, Stage
from main import TrainerSystem


# 训练身份选项
AUDIENCE_OPTIONS = [
    (Audience.MINOR, "青少年（仅未成年安全场景）"),
    (Audience.ADULT, "成年人（全部场景）"),
]

# 阶段中文名（仅用于展示）
STAGE_NAMES = {
    Stage.OPENING: "开场",
    Stage.PRESSURE: "施压对峙",
    Stage.RESOLVE: "通关",
    Stage.DEADLOCK: "失控",
    Stage.END: "到时",
}


def print_history(history):
    """打印当前对话历史（NPC：xxx / 我：xxx）"""
    if not history:
        print("  （暂无对话历史）")
        return
    for msg in history:
        name = "NPC" if msg["role"] == "ai" else "我"
        print(f"  {name}：{msg['content']}")


def print_card(card):
    """打印进场景预生成的教学卡"""
    print("=" * 50)
    print(f"【教学卡】{card.title}")
    print(f"  什么时候用：{card.when}")
    print(f"  怎么用：{card.how}")
    print(f"  为什么：{card.why}")
    print(f"  话术示例：{card.example}")
    print("=" * 50)


def print_turn(turn):
    """打印一次回合的完整结果（评分 + 扮演回应 + 提示）"""
    print("-" * 50)
    print(f"总分：{turn.score.total_score}/100")
    print(f"对峙值：{turn.confrontation_value}/100")
    if turn.score.red_line_hits:
        print(f"⚠️ 命中红线：{'、'.join(turn.score.red_line_hits)}")
    print("各维度：")
    for dim_name, dim_score in turn.score.dimensions.items():
        if dim_score > 0:
            print(f"  ✓ {dim_name}：{dim_score}")
    print(f"反馈：{turn.score.feedback}")
    if turn.teaching_hint:
        print(f"实时提示：{turn.teaching_hint}")
    print(f"NPC：{turn.ai_reply}")
    print(f"阶段：{STAGE_NAMES.get(turn.next_stage, turn.next_stage)}")
    print("-" * 50)


def print_review(review):
    """打印会话复盘结果"""
    print("=" * 50)
    print("【会话复盘】")
    print(f"目标达成：{'是' if review.goal_achieved else '否'}")
    print(f"达成度：{review.achievement_score}/100")
    print(f"总结：{review.summary}")
    if review.weak_points:
        print("薄弱点：")
        for w in review.weak_points:
            print(f"  - {w}")
    print("=" * 50)


def choose(options, prompt, invalid_msg):
    """让用户按数字选择一项，返回该项的 (id/值)。"""
    print(prompt)
    for i, (_, name) in enumerate(options, start=1):
        print(f"  {i}. {name}")
    while True:
        choice = input("请输入数字：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print(invalid_msg)


def main():
    print("=" * 50)
    print("欢迎使用 safe-trainer 多 Agent 后端（安全对线训练场）")
    print("=" * 50)
    print("本工具串起：评分 Agent + 场景扮演 Agent + 教学 Agent + 复盘 Agent。")
    print("你扮演「我」，NPC 的回应由扮演 Agent 自动生成。")
    print()

    # 初始化训练系统
    system = TrainerSystem()

    # 步骤1：选择训练身份（决定可选场景）
    audience, audience_name = choose(
        AUDIENCE_OPTIONS,
        "【身份】请选择你的训练身份：",
        "输入无效，请重新输入数字",
    )
    print(f"已选择身份：{audience_name}")
    print()

    # 步骤2：列出（过滤后的）场景，选择其一
    scenarios = system.scenario_store.list_scenarios(audience)
    scenario_options = [(s["id"], f"{s['title']}（{s['premise']}）") for s in scenarios]
    scenario_id, scenario_name = choose(
        scenario_options,
        "【场景】请选择要练习的场景：",
        "输入无效，请重新输入数字",
    )
    print(f"已选择场景：{scenario_name}")
    print()

    # 步骤3：开新会话（落库 + NPC 开场白 + 教学卡），生成唯一会话ID
    user_id = "cli_user_001"
    session_id = f"cli_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"用户ID：{user_id} | 会话ID：{session_id}")
    print()

    opening, card = system.start_session(user_id, session_id, scenario_id, audience)
    print_card(card)
    print(f"【{scenario_name}】NPC：{opening}")
    print()

    # 交互说明
    print("输入提示：")
    print("  - 直接输入文字：作为「我」的回应，触发完整回合（评分+NPC回应）")
    print("  - 输入 clear：清空当前会话（不删落库数据）")
    print("  - 输入 end：手动结束会话并触发复盘")
    print("  - 输入 exit / quit：直接退出（不触发复盘）")
    print()

    # 主循环
    while True:
        # 每次循环先展示当前对话历史
        history = system.memory.get_context(session_id)
        print("当前对话历史：")
        print_history(history)
        print()

        try:
            raw = input("请输入你的回应：").strip()
        except EOFError:
            # stdin 被读完（例如管道测试输入流结束），视为正常退出。
            print("\n输入流已结束，退出。")
            break
        if not raw:
            continue  # 空输入忽略

        low = raw.lower()
        if low in ("exit", "quit"):
            print("已退出，再见！")
            break
        elif low == "clear":
            system.clear_session(session_id)
            print("已清空当前会话（短时记忆与计数）")
            continue

        # 其余输入视为用户回应，走完整回合（评分 + 扮演 + 教学 + 阶段判定）
        turn = system.handle_turn(
            user_id, session_id, scenario_id, audience, raw
        )
        print_turn(turn)
        print()

        # 终局自动触发复盘
        if turn.next_stage in (Stage.RESOLVE, Stage.DEADLOCK, Stage.END):
            review = system.end_session(user_id, session_id, scenario_id, audience)
            print_review(review)
            print("本场训练已结束。可重新运行 cli.py 再开一局。")
            break


if __name__ == "__main__":
    main()
