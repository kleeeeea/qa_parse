import csv
import os
import re
from dataclasses import asdict

from dataclass_ import AnswerSpanRow, columns
from exam_formats import PRAXIS_READING, ExamFormat
from stage import Stage
from tests.fixture._constants import mineruparsed
from _1_get_questions_mainbody import GetQuestionsMainbodyStage, slice_mainbody
from _2_split_question_main_body_into_consecutive_problem_spans import (
    SplitQuestionMainbodyIntoIndividualQuestionsStage,
    split_into_items,
)

answerspan_output_csv_basename = 'answer_spans.csv'
answerspan_output_columns = columns(AnswerSpanRow)

# 一条答案的起始行由 exam_format.answer_header_re 决定：
# praxis: "1. d. Only choice d …"；plt 短答题: "## 1. Sample Response …"。

# Top-level markdown headers — used as section boundaries.
TOP_LEVEL_HEADER_RE = re.compile(r'^#\s+(.*)$')
# Sub-labels that may appear inside an answer section and should NOT end it.
IN_SECTION_TOP_LEVEL_RE = re.compile(r'^\s*(Passage|Source)\s+\d+\s*$', re.IGNORECASE)
# A top-level header that contains this phrase opens the answer section.
ANSWERS_SECTION_MARKER_RE = re.compile(r'Answers and Explanations', re.IGNORECASE)


def _is_answer_mainbody_start(line):
    # 答案主体起点：含 "Answers and Explanations" 的顶级标题
    m = TOP_LEVEL_HEADER_RE.match(line)
    return bool(m and ANSWERS_SECTION_MARKER_RE.search(m.group(1)))


def _is_answer_mainbody_end(line):
    # 答案主体终点：下一个顶级标题——但 Passage/Source 子标题不算（留在答案内），
    # 另一段 "Answers and Explanations" 标题也不算（同属答案区）
    m = TOP_LEVEL_HEADER_RE.match(line)
    if not m:
        return False
    header_text = m.group(1).strip()
    if ANSWERS_SECTION_MARKER_RE.search(header_text):
        return False
    return not IN_SECTION_TOP_LEVEL_RE.match(header_text)


def _split_markdown_into_answer_spans(md_text, exam_format: ExamFormat = PRAXIS_READING,
                                      expected_end_num=None):
    """先复用 slice_mainbody 切出答案主体（"Answers and Explanations" 标题起，
    到下一个非 Passage/Source 顶级标题止；没有答案区则空切片），再复用 _2 的
    split_into_items：答案号从 1 严格连续递增到 expected_end_num（题目数量），
    把答案解析里引用的题号挡在外面。expected_end_num 为 None 时不设上界。
    """
    lines = md_text.splitlines()
    start, end = slice_mainbody(
        lines, _is_answer_mainbody_start, _is_answer_mainbody_end,
        default_start=len(lines))

    def _detect_answer_start(line):
        m = exam_format.answer_mainbody_start_re.match(line)
        return int(m.group(1)) if m else None

    return [{'num': num, 'lines': item_lines}
            for num, item_lines in split_into_items(
                lines[start:end], _detect_answer_start,
                expected_start_num=1, expected_end_num=expected_end_num)]


def _serialize_span(span):
    return '\n'.join(span['lines']).strip()


class SplitMineruParsedMdIntoAnswerSpansStage(Stage):
    # …/{mineru任务目录}/full.md -> …/{mineru任务目录}/answer_spans.csv
    output_basename = answerspan_output_csv_basename

    def _produce(self, output_path, current_mineruparsed):
        with open(current_mineruparsed) as f:
            md_text = f.read()

        # 先读题目集合（若已产出）：既用于答案号上界（1..题目数量），也用于交叉核对。
        # 从输入 md 沿 _1_ -> _2_ 的 derive 链动态推导 individual_questions.csv 的路径
        expected = set()
        individual_question_output_csv = SplitQuestionMainbodyIntoIndividualQuestionsStage().derive_output_path(
            GetQuestionsMainbodyStage().derive_output_path(current_mineruparsed))
        if os.path.exists(individual_question_output_csv):
            with open(individual_question_output_csv) as f:
                for row in csv.DictReader(f):
                    try:
                        expected.add(int(row['question_number']))
                    except (KeyError, TypeError, ValueError):
                        pass

        spans = _split_markdown_into_answer_spans(
            md_text, self.exam_format, expected_end_num=len(expected) or None)

        # split_into_items 已保证答案号严格递增唯一；dedup/sort 留作防御性兜底。
        seen = set()
        deduped = []
        for s in spans:
            if s['num'] in seen:
                continue
            seen.add(s['num'])
            deduped.append(s)
        deduped.sort(key=lambda s: s['num'])

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=answerspan_output_columns)
            writer.writeheader()
            for s in deduped:
                writer.writerow(asdict(AnswerSpanRow(
                    question_number=str(s['num']),
                    answer=_serialize_span(s),
                )))

        missing = sorted(expected - seen)
        extra = sorted(seen - expected) if expected else []
        print(f'wrote {len(deduped)} answer spans to {output_path}')
        if missing:
            print(f'  missing answers for questions: {missing}')
        if extra:
            print(f'  extra answers not in individual_questions.csv: {extra}')


if __name__ == '__main__':
    SplitMineruParsedMdIntoAnswerSpansStage().run(mineruparsed)
