# -*- coding: utf-8 -*-
"""
cli.py - 命令行入口

提供交互式命令行，用于在没有前端的情况下手动测试完整训练闭环。
一条用户输入 → 完整回合（评分 + 王阿姨回应 + 实时提示 + 阶段判定）。
"""

import sys

# Windows 控制台默认用 GBK 编码，直接打印/读取中文会乱码；
# 这里在入口处强制 stdin / stdout 都使用 UTF-8，保证中文正常显示与输入。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

import config
from main import TrainerSystem


# 约束选项列表：（约束ID, 中文名）
CONSTRAINT_OPTIONS = [
    ("want_maintain", "想维持关系"),
    ("endure_but_record", "能忍但记账"),
    ("dont_care", "无所谓"),
    ("want_cutoff", "想断联"),
]


def print_history(history):
    """打印当前对话历史（王阿姨：xxx / 我：xxx）"""
    if not history:
        print("  （暂无对话历史）")
        return
    for msg in history:
        name = "王阿姨" if msg["role"] == "ai" else "我"
        print(f"  {name}：{msg['content']}")


def print_turn(turn):
    """打印一次回合的完整结果（评分 + 扮演回应 + 提示）"""
    print("=" * 40)
    print(f"总分：{turn.score.total_score}/{config.SCORE_MAX}")
    print("各维度：")
    for dim_name, dim_score in turn.score.dimensions.items():
        print(f"  - {dim_name}：{dim_score}")
    print(f"反馈：{turn.score.feedback}")
    if turn.teaching_hint:
        print(f"实时提示：{turn.teaching_hint}")
    print(f"王阿姨：{turn.ai_reply}")
    print("=" * 40)


def print_review(review):
    """打印会话复盘结果"""
    print("=" * 40)
    print("【会话复盘】")
    print(f"目标达成：{'是' if review.goal_achieved else '否'}")
    print(f"达成度：{review.achievement_score}/100")
    print(f"总结：{review.summary}")
    if review.weak_points:
        print("薄弱点：")
        for w in review.weak_points:
            print(f"  - {w}")
    print("=" * 40)


def main():
    # 欢迎信息和使用说明
    print("=" * 50)
    print("欢迎使用 safe-trainer 多 Agent 后端（v2 完整闭环）")
    print("=" * 50)
    print("本工具串起：评分 Agent + 场景扮演 Agent + 教学 Agent + 复盘 Agent。")
    print("你扮演「我」，王阿姨的回应由扮演 Agent 自动生成。")
    print()

    # 场景选择：目前只有一个场景，直接默认选中
    print("【场景】当前只有一个场景，默认选中：王阿姨催婚")
    print("  场景描述：过年聚餐，亲戚王阿姨当众催婚，问你什么时候结婚")
    print()

    # 约束选择：列出4个选项让用户输入数字
    print("【约束】请选择你本次想练习的目标：")
    for i, (_, name) in enumerate(CONSTRAINT_OPTIONS, start=1):
        print(f"  {i}. {name}")
    while True:
        choice = input("请输入数字（1-4）：").strip()
        if choice in ("1", "2", "3", "4"):
            break
        print("输入无效，请输入 1-4 之间的数字")
    constraint = CONSTRAINT_OPTIONS[int(choice) - 1][0]
    print(f"已选择约束：{CONSTRAINT_OPTIONS[int(choice) - 1][1]}")
    print()

    # 初始化训练系统，生成固定用户ID与测试会话ID
    system = TrainerSystem()
    user_id = "cli_user_001"
    session_id = "test_session_001"
    print(f"用户ID：{user_id} | 会话ID：{session_id}")
    print()

    # 交互说明
    print("输入提示：")
    print("  - 直接输入文字：作为「我」的回应，触发完整回合（评分+王阿姨回应）")
    print("  - 输入 ai:xxx：把 xxx 作为王阿姨的回应手动加入历史（降级用，一般用不到）")
    print("  - 输入 clear：清空当前会话历史")
    print("  - 输入 end：结束会话并触发复盘")
    print("  - 输入 exit / quit：直接退出（不触发复盘）")
    print()

    # 主循环
    while True:
        # 每次循环先展示当前对话历史
        history = system.memory.get_context(session_id)
        print("-" * 50)
        print("当前对话历史：")
        print_history(history)
        print("-" * 50)

        try:
            raw = input("请输入你的回应：").strip()
        except EOFError:
            # stdin 被读完（例如管道测试输入流结束），视为正常退出。
            # 避免真实交互与自动化测试在结束时抛异常。
            print("\n输入流已结束，退出。")
            break
        if not raw:
            continue  # 空输入忽略

        low = raw.lower()
        if low in ("exit", "quit"):
            print("已退出，再见！")
            break
        elif low == "end":
            review = system.end_session(user_id, session_id, "wang_ayi_cuihun", constraint)
            print_review(review)
            continue
        elif low == "clear":
            system.clear_session(session_id)
            print("已清空当前会话历史")
            continue
        elif raw.startswith("ai:"):
            ai_content = raw[3:].strip()
            if not ai_content:
                print("ai: 后面不能为空")
                continue
            system.add_ai_message(session_id, ai_content)
            print("已把王阿姨的回应手动加入历史")
            continue

        # 其余输入视为用户回应，走完整回合（评分 + 扮演 + 教学 + 阶段判定）
        turn = system.handle_turn(
            user_id, session_id, "wang_ayi_cuihun", constraint, raw
        )
        print_turn(turn)
        print()


if __name__ == "__main__":
    main()
