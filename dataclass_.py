"""Frozen dataclasses 约束 pipeline 中每个 CSV 的行 schema。

- 列名由字段定义唯一导出（columns()），不再手维护字符串列表；
- Row(**row) 构造即校验：上游 CSV 多列/缺列/改名会直接 TypeError；
- frozen=True 保证行对象在写出前不会被改动。

CSV 落盘后所有值都是字符串，所以字段统一标注为 str，
构造方需自行 str() 数值字段（如 question_number）。
"""
from dataclasses import dataclass, fields


def columns(row_cls) -> list[str]:
    """Row dataclass -> CSV 列名列表（即 DictWriter 的 fieldnames）。"""
    return [f.name for f in fields(row_cls)]

# 共享字段抽成 mixin 基类，避免在多个 Row 里重复定义同名字段。
# 注意：dataclass 按 MRO 逆序（基类在前）收集字段，所以子类的基类列表
# 要按「想要的列序」反着写，才能保持 CSV 列顺序不变。
@dataclass(frozen=True)
class _HasQuestionNumber:
    question_number: str


@dataclass(frozen=True)
class _HasPassageAndQuestion:
    passage: str
    question: str


@dataclass(frozen=True)
class _HasAnswer:
    answer: str


@dataclass(frozen=True)
class QuestionSpanRow:
    """_2_ question_spans.csv：一行 = 一个 passage + 其题目组成的 span。"""
    spans: str


@dataclass(frozen=True)
class IndividualQuestionRow(_HasPassageAndQuestion, _HasQuestionNumber):
    """_3_ individual_questions.csv：一行 = 一道题（passage 随行冗余）。

    列序：question_number, passage, question, original_page_screenshot_paths
    """
    original_page_screenshot_paths: str


@dataclass(frozen=True)
class AnswerSpanRow(_HasAnswer, _HasQuestionNumber):
    """_4_ answer_spans.csv：一行 = 一道题的答案+解析。

    列序：question_number, answer
    """


@dataclass(frozen=True)
class ProblemAndAnswerRow(_HasAnswer, _HasPassageAndQuestion, _HasQuestionNumber):
    """_5_ problems_and_answers.csv：题目与答案按题号 outer-join 后的一行。

    列序：question_number, passage, question, answer,
          question_page_screenshot_paths, answer_page_screenshot_paths
    """
    question_page_screenshot_paths: str
    answer_page_screenshot_paths: str


# prompts.csv 目前是 joined CSV 的逐行透传，schema 相同，直接复用。
PromptRow = ProblemAndAnswerRow
