# 把得到第一个span开头之前 的所有逻辑 移动到这里 产生单独的md output
import os
import re

from exam_formats import PRAXIS_READING, ExamFormat, question_number_match
from stage import Stage
from tests.fixture._constants import mineruparsed


def _get_questions_mainbody(md_text, exam_format: ExamFormat):
    """Slice the markdown down to the questions main body.

    起点：第一个 span trigger 行（praxis: "Use the following passage…"；
    plt: "## Case History 1"）或题号为 1 的题目行，二者取更早者——
    封面、限时说明、Directions 等前言全部丢弃。
    终点：mainbody_end_re 命中的标题之前（praxis: "# …Answers and
    Explanations"，答案区及后续 Writing/Math 区段全部丢弃）；
    mainbody_end_re 为 None 表示题目文档没有答案区（题/答分开两份
    PDF），主体直到文件尾。
    """
    lines = md_text.splitlines()
    # 处理第一个题目没有Passage， 直接是
    # 1.{question}
    # 的情况：起点取「第一个 trigger 行」和「题号为 1 的题目行」中更早出现者
    def _is_mainbody_start(l):
        if exam_format.span_trigger_re.match(l):
            return True
        return question_number_match(exam_format, l) == 1

    start = next(
        (i for i, l in enumerate(lines) if _is_mainbody_start(l)), 0)
    end = len(lines)
    if exam_format.mainbody_end_re is not None:
        for i in range(start, len(lines)):
            if exam_format.mainbody_end_re.match(lines[i]):
                end = i
                break
    # 剥掉主体末尾的空行和孤立页码行（mineru 把页脚页码解析成单独一行，
    # 否则会挂在最后一题的题干尾部）
    while end > start and (not lines[end - 1].strip()
                           or re.fullmatch(r'\s*\d+\s*', lines[end - 1])):
        end -= 1
    return '\n'.join(lines[start:end]).strip() + '\n'


class GetQuestionsMainbodyStage(Stage):
    # …/{dataset}/{mineru任务目录}/full.md -> …/{dataset}/{mineru任务目录}/questions_mainbody.md
    # output to the same root（输入所在目录，不再依赖全局输出根目录）
    output_basename = 'questions_mainbody.md'

    def _produce(self, output_path, input_document):
        with open(input_document) as f:
            md_text = f.read()
        mainbody = _get_questions_mainbody(md_text, self.exam_format)
        with open(output_path, 'w') as f:
            f.write(mainbody)
        print(f'wrote {len(mainbody.splitlines())} lines to {output_path}')


if __name__ == '__main__':
    GetQuestionsMainbodyStage().run(mineruparsed)
