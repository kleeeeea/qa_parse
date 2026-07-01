import csv
import json
from pathlib import Path

from _1_get_questions_mainbody import GetQuestionsMainbodyStage
from _2_parse_questions import (
    SplitQuestionMainbodyIntoIndividualQuestionsStage,
)
from parse_evaluation.exam_formats import ExamFormat
from parse_evaluation.exam_formats import get_exam_format
from parse_evaluation._3_join_problems_and_answers import JoinProblemsAndAnswersStage
from parse_evaluation.exam_formats import EXAM_FORMAT_BY_NAME
from parse_evaluation.exam_formats import PLT
from parse_evaluation.exam_formats import PLTUnordered
from parse_evaluation.dataclass_ import EvaluationRecord
from parse_evaluation.dataclass_ import columns


def _infer_answer_input_document(question_input_document: str) -> str:
    question_path = Path(question_input_document)
    question_dir = question_path.parent
    question_dir_name = question_dir.name

    if 'question' not in question_dir_name:
        return str(question_path)

    parent_dir = question_dir.parent
    answer_prefix = question_dir_name.split('question', 1)[0] + 'answer'
    exact_answer_dir = parent_dir / question_dir_name.replace(
        'question', 'answer', 1)

    candidates = []
    exact_answer_path = exact_answer_dir / question_path.name
    if exact_answer_path.is_file():
        candidates.append(exact_answer_path)

    for sibling in parent_dir.iterdir():
        if not sibling.is_dir():
            continue
        if not sibling.name.startswith(answer_prefix):
            continue
        answer_path = sibling / question_path.name
        if answer_path.is_file() and answer_path not in candidates:
            candidates.append(answer_path)

    if len(candidates) == 1:
        return str(candidates[0])
    if candidates:
        raise ValueError(
            'multiple answer documents matched '
            f'{question_input_document}: {candidates}'
        )
    raise FileNotFoundError(
        'could not infer answer_input_document from '
        f'{question_input_document}'
    )



def run_parse_evaluation_pipeline(
    question_input_document: str,
    answer_input_document: str | None = None,
    exam_format_str: str | None = 'plt',
    exam_format: ExamFormat | None = None,
    *,
    skip_if_output_exists: bool = True,
) -> str:
    if (
        answer_input_document in EXAM_FORMAT_BY_NAME
        and exam_format_str == 'plt'
        and not Path(answer_input_document).exists()
    ):
        exam_format_str = answer_input_document
        answer_input_document = None

    if answer_input_document is None:
        answer_input_document = _infer_answer_input_document(
            question_input_document)
    # 允许传入卷型「类」（如 PLT），统一实例化——下游按实例方法调用 exam_format
    if isinstance(exam_format, type):
        exam_format = exam_format()
    if exam_format is None:
        exam_format = (
            EXAM_FORMAT_BY_NAME[exam_format_str] if exam_format_str else None
        )

    # 未显式指定时，从题目文档内容自动推断卷型
    if exam_format is None:
        exam_format = get_exam_format(question_input_document)
        print(f'inferred exam format: {exam_format.name}')
    from parse_evaluation._1_parse_answers import SplitMineruParsedMdIntoAnswerSpansStage
    answer_output_document = SplitMineruParsedMdIntoAnswerSpansStage(
        exam_format=exam_format,
        skip_if_output_exists=skip_if_output_exists,
    ).run(
        answer_input_document
    )
    # questions_mainbody_md = GetQuestionsMainbodyStage(
    #     exam_format=exam_format,
    #     skip_if_output_exists=skip_if_output_exists,
    # ).run(question_input_document)
    individual_question_csv = SplitQuestionMainbodyIntoIndividualQuestionsStage(
        exam_format=exam_format,
        skip_if_output_exists=skip_if_output_exists,
    ).run(question_input_document)
    join_stage = JoinProblemsAndAnswersStage(
        exam_format=exam_format,
        skip_if_output_exists=skip_if_output_exists,
    )
    joined_csv = join_stage.run(individual_question_csv, answer_output_document)
    # evaluation_records.jsonl 路径由真实的 join 输出导出（不在调用方反推
    # individual_questions.csv），直接返回给调用方收集。
    return join_stage.derive_evaluation_record_output_path(joined_csv)
    # joined_output_csv = os.path.join(
    #     os.path.dirname(individual_question_csv), joined_output_csv_basename)
    #
    # # prompts.csv 与 joined 输出同目录
    # prompts_output_csv = os.path.join(os.path.dirname(joined_output_csv), 'prompts.csv')
    # # keep the original metadata columns — prompts.csv is a superset of the joined
    # # CSV with the derived `id` and `prompt` fields added on top.
    # # 行 schema 统一定义在 dataclass_.py，全流水线复用（构造即校验、frozen 不可变）
    # prompts_output_columns = columns(PromptRow)
    #
    # os.makedirs(os.path.dirname(prompts_output_csv), exist_ok=True)
    # _rows_written = 0
    # with open(joined_output_csv, newline='') as _f_in, open(prompts_output_csv, 'w', newline='') as _f_out:
    #     _reader = csv.DictReader(_f_in)
    #     _writer = csv.DictWriter(_f_out, fieldnames=prompts_output_columns)
    #     _writer.writeheader()
    #     for _row in _reader:
    #         _writer.writerow(asdict(PromptRow(**_row)))
    #         _rows_written += 1
    # print(f'wrote {_rows_written} prompts to {prompts_output_csv}')(




def _write_records_csv(records, csv_path, fieldnames):
    """把 records（dict 列表）写成 CSV；options 是 dict/list 时序列化成 JSON 字符串。"""
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            row = dict(rec)
            if isinstance(row.get('options'), (dict, list)):
                row['options'] = json.dumps(row['options'], ensure_ascii=False)
            writer.writerow({k: row.get(k, '') for k in fieldnames})


def main():
    # 遍历 praxis_plt_sections/plt_1 .. plt_10，对每个数据集跑整条管线。
    sections_dir = (
        Path(__file__).resolve().parent
        / 'tests' / 'fixture' / 'praxis_plt_sections'
    )
    # run_parse_evaluation_pipeline 返回各数据集的 evaluation_records.jsonl 路径，逐个收集后合并
    record_jsonl_paths: list[str] = []
    for n in range(1, 11):
        plt_dir = sections_dir / f'plt_{n}'
        # 每个数据集的题目 mineru 产物：plt_N/plt_N_question.pdf-<uuid>/full.md
        question_full_mds = sorted(plt_dir.glob('*_question.pdf-*/full.md'))
        if len(question_full_mds) != 1:
            raise FileNotFoundError(
                    f'expected exactly one question full.md under {plt_dir}, '
                    f'found {len(question_full_mds)}: {question_full_mds}'
            )
        question_input_document = str(question_full_mds[0])
        print(f'=== running pipeline for plt_{n} ===')
        # 每步返回输出路径并作为下一步的输入；输出已存在时各步自动跳过（幂等）
        # 不传 exam_format —— 由题目文档内容自动推断
        # 单个数据集失败不应中断整批：捕获、打印、继续下一个。
        try:
            records_jsonl = run_parse_evaluation_pipeline(
                question_input_document,
                exam_format=PLTUnordered() if n in {1,2,3,6} else PLT(),
                skip_if_output_exists=False,
            )
        except Exception as exc:
            print(f'!!! plt_{n} failed: {type(exc).__name__}: {exc}')
            records_jsonl = None
        # pipeline 直接返回本数据集产出的 jsonl 路径，无需在此反推
        if records_jsonl and Path(records_jsonl).is_file():
            record_jsonl_paths.append(records_jsonl)

    # 合并所有数据集的 jsonl 到一个总文件（每行一条记录，直接逐行透传），
    # 顺便解析出每条记录，供下面导出 CSV / 按题型拆分复用。
    merged_path = sections_dir / 'evaluation_records_merged.jsonl'
    merged_records: list[dict] = []
    with open(merged_path, 'w', encoding='utf-8') as out:
        for jsonl_path in record_jsonl_paths:
            with open(jsonl_path, encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    out.write(line if line.endswith('\n') else line + '\n')
                    merged_records.append(json.loads(line))
    print(f'merged {len(merged_records)} records from {len(record_jsonl_paths)} '
          f'dataset(s) into {merged_path}')

    # 同一批记录再导出一份 CSV（列名取自 EvaluationRecord 字段）。
    fieldnames = columns(EvaluationRecord)
    merged_csv_path = merged_path.with_suffix('.csv')
    _write_records_csv(merged_records, merged_csv_path, fieldnames)
    print(f'wrote {len(merged_records)} records to {merged_csv_path}')

    # 按 EvaluationRecord.type 拆分：每种题型单独产出一份 jsonl + csv。
    by_type: dict[str, list[dict]] = {}
    for rec in merged_records:
        by_type.setdefault(rec.get('type') or 'unknown', []).append(rec)
    for rtype, recs in sorted(by_type.items()):
        type_jsonl = sections_dir / f'evaluation_records_{rtype}.jsonl'
        with open(type_jsonl, 'w', encoding='utf-8') as out:
            for rec in recs:
                out.write(json.dumps(rec, ensure_ascii=False) + '\n')
        _write_records_csv(recs, type_jsonl.with_suffix('.csv'), fieldnames)
        print(f'  [{rtype}] {len(recs)} records -> '
              f'{type_jsonl.name} + {type_jsonl.with_suffix(".csv").name}')


if __name__ == '__main__':
    main()
