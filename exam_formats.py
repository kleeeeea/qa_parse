"""卷型相关的解析规则，参数化成 frozen dataclass。

pipeline 各步（_1_/_2_/_3_/_4_）只依赖 ExamFormat 字段，
新增卷型时在这里加一个实例即可，不需要复制脚本。
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExamFormat:
    name: str
    # 开启一个新 span 的行（praxis: "Use the following passage…"；
    # plt: "## Case History N" / "## Discrete Multiple-Choice Questions" 节标题）
    span_trigger_re: re.Pattern
    # 题目行；题号取第一个非 None 捕获组（见 question_number_match）
    question_line_re: re.Pattern
    # 声明题号范围的行：group(1)=起始题号，group(2)=结束题号（可缺省=单题）。
    # praxis 在 trigger 行上（"… questions 50 through 53."），
    # plt 在 Directions 行上（"Directions: Questions 7–18 are not related…"）。
    # 必须锚定到该行特有的前缀，避免普通正文误中。
    question_range_re: re.Pattern
    # 答案区里一条答案的起始行（plt 的短答题答案是 "## 1. Sample Response…" 二级标题）
    answer_header_re: re.Pattern
    # 题目主体的终止标题；None 表示题目文档没有答案区（题/答分开两份 PDF），主体到文件尾
    mainbody_end_re: re.Pattern | None


def question_number_match(exam_format: ExamFormat, line: str) -> int | None:
    """题目行 -> 题号；非题目行 -> None。

    question_line_re 可能是多分支正则（如 plt 的 "## Question N" 与 "N. "），
    题号取第一个非 None 的捕获组。
    """
    m = exam_format.question_line_re.match(line)
    if not m:
        return None
    return int(next(g for g in m.groups() if g is not None))


PRAXIS_READING = ExamFormat(
    name='praxis_reading',
    span_trigger_re=re.compile(r'^\s*Use the following passage', re.IGNORECASE),
    # passage 行号边注（"5 Massachusetts, and…"）没有点号，不会误中
    question_line_re=re.compile(r'^\s*(\d+)\.\s'),
    question_range_re=re.compile(
        r'^\s*Use the following passage.*?questions?\s+(\d+)'
        r'(?:\s+(?:and|through)\s+(\d+))?', re.IGNORECASE),
    answer_header_re=re.compile(r'^[ \t]*(\d+)\.\s'),
    mainbody_end_re=re.compile(r'^#\s+.*Answers and Explanations', re.IGNORECASE),
)

PLT = ExamFormat(
    name='plt',
    span_trigger_re=re.compile(
        r'^##\s+(?:Case History \d+|Discrete Multiple-Choice Questions)\s*$'),
    # 短答题题号在二级标题里（"## Question 19"），选择题是 "N. " 行
    question_line_re=re.compile(r'^##\s+Question\s+(\d+)\s*$|^\s*(\d+)\.\s'),
    # "Directions: Questions 1 through 3 …" / "Directions: Questions 7–18 …"
    question_range_re=re.compile(
        r'^Directions:.*?Questions?\s+(\d+)\s*(?:through|–|—|-)\s*(\d+)',
        re.IGNORECASE),
    # 短答题答案："## 1. Sample Response that receives a score of 2:"；
    # 选择题答案："7. B …"
    answer_header_re=re.compile(r'^(?:##\s+)?(\d+)\.\s'),
    # 题目 PDF 末尾附了答题卡（姓名/出生日期/涂卡区等 HTML 表格），
    # 从 "## Diagnostic Test Form" 标题起全部不是题目
    mainbody_end_re=re.compile(r'^##\s+Diagnostic Test Form\b'),
)
