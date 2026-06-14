import csv
import os
from dataclasses import asdict

from dataclass_ import ProblemAndAnswerRow, columns
from tests.fixture._constants import mineruparsed
from _1_get_questions_mainbody import derive_questions_mainbody_output_md
from _2_split_question_main_body_into_consecutive_problem_spans import derive_questionspan_output_csv
from _3_split_consecutive_problem_spans_into_individual_questions import derive_individual_question_output_csv
from _4_split_mineru_parsed_md_into_consecutive_answer_spans import derive_answerspan_output_csv

joined_output_csv_basename = 'problems_and_answers.csv'
joined_output_columns = columns(ProblemAndAnswerRow)


def _load_by_question_number(csv_path):
    """Load a CSV keyed by integer question_number."""
    by_q = {}
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            try:
                qnum = int(row['question_number'])
            except (KeyError, TypeError, ValueError):
                continue
            by_q[qnum] = row
    return by_q


def derive_joined_output_csv(current_individual_question_csv):
    # …/{mineru任务目录}/individual_questions.csv -> …/{mineru任务目录}/problems_and_answers.csv
    return os.path.join(
        os.path.dirname(os.path.abspath(current_individual_question_csv)),
        joined_output_csv_basename)


def join_problems_and_answers(current_individual_question_csv, current_answerspan_csv, skip_if_output_exists=True) -> str:
    """Outer-join the individual-questions CSV with the answer-spans CSV on
    question_number. Each output row pairs a question's passage + stem +
    choices with its corresponding answer + explanation.

    Rows present in only one input still get emitted (the other side's
    columns are left empty), so missing-side mismatches are visible in the
    output rather than silently dropped.
    """
    joined_output_csv = derive_joined_output_csv(current_individual_question_csv)
    if skip_if_output_exists and os.path.exists(joined_output_csv):
        print(f'skip: {joined_output_csv} already exists')
        return joined_output_csv
    questions = _load_by_question_number(current_individual_question_csv)
    answers = _load_by_question_number(current_answerspan_csv)
    all_qnums = sorted(set(questions) | set(answers))

    out_dir = os.path.dirname(joined_output_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(joined_output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=joined_output_columns)
        writer.writeheader()
        for qnum in all_qnums:
            q = questions.get(qnum) or {}
            a = answers.get(qnum) or {}
            writer.writerow(asdict(ProblemAndAnswerRow(
                question_number=str(qnum),
                passage=q.get('passage', ''),
                question=q.get('question', ''),
                answer=a.get('answer', ''),
                question_page_screenshot_paths=q.get('original_page_screenshot_paths', ''),
                answer_page_screenshot_paths=a.get('original_page_screenshot_paths', ''),
            )))

    missing_answers = sorted(set(questions) - set(answers))
    missing_questions = sorted(set(answers) - set(questions))
    print(f'wrote {len(all_qnums)} joined rows to {joined_output_csv}')
    if missing_answers:
        print(f'  questions without a matching answer: {missing_answers}')
    if missing_questions:
        print(f'  answers without a matching question: {missing_questions}')
    return joined_output_csv


if __name__ == '__main__':
    # 题目侧沿 _1_ -> _2_ -> _3_ 的 derive 链从输入 md 动态推导；
    # 答案侧用 _4_ 的 derive
    individual_question_output_csv = derive_individual_question_output_csv(
        derive_questionspan_output_csv(
            derive_questions_mainbody_output_md(mineruparsed)))
    join_problems_and_answers(
        individual_question_output_csv,
        derive_answerspan_output_csv(mineruparsed))
