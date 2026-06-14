import csv
from dataclasses import asdict

from _1_get_questions_mainbody import GetQuestionsMainbodyStage
from dataclass_ import IndividualQuestionRow
from dataclass_ import columns
from exam_formats import ExamFormat
from exam_formats import PRAXIS_READING
from exam_formats import question_number_safe_search
from stage import Stage
from tests.fixture._constants import mineruparsed

individual_question_output_csv_basename = 'individual_questions.csv'
output_csv_columns = columns(IndividualQuestionRow)
# example:
sample_questions_that_should_be_in_the_same_span_because_they_refer_to_the_same_passage = """
Use the following passage to answer questions 1 and 2.

Of the numerous American automotive pioneers, perhaps among the best known are Charles and Frank Duryea. Beginning their work of automobile building in Springfield,
5 Massachusetts, and, after much rebuilding, they constructed their first successful vehicle in 1892 and 1893. No sooner was this finished than Frank, working alone, began work on a second vehicle having a two-cylinder engine. With this
10 automobile, sufficient capital was attracted in 1895 to form the Duryea Motor Wagon Company in which both brothers were among the stockholders and directors. A short time after the formation of the company, this second
15 automobile was entered by the company in the Chicago Times-Herald automobile race on Thanksgiving Day, November 28, 1895, where Frank Duryea won a victory over the other five contestants—two electric automobiles and
20 three Benz machines imported from Germany.

Source: Excerpt from The 1893 Duryea Automobile by Don H. Berkebile.

Which of the following is the best summary of the passage?
a. There were many automotive pioneers in America, but the best known were the brothers Charles and Frank Duryea, who began building automobiles in Springfield, Massachusetts. b. Charles and Frank Duryea were among the best-known American automotive pioneers, but Frank was more famous than his brother Charles because Frank won the Chicago Times-Herald automobile race.
c. On Thanksgiving Day, November 28, 1895, Frank Duryea won the Chicago Times-Herald automobile race over five other contestants: two electric automobiles and three Benz machines from Germany.
d. Charles and Frank Duryea were pioneering automobile builders, and Frank developed a profitable two-cylinder engine vehicle with which he won the Chicago Times-Herald automobile race.
e. Although Frank Duryea developed a two-cylinder engine vehicle, both he and his brother Charles profited from it because it earned them the capital to start the Duryea Motor Wagon Company.

In the passage, the author describes the kinds of cars Frank Duryea defeated in the Chicago Times-Herald automobile race in order to
a. show that the best automobiles in the world are built in Springfield, Massachusetts.
b. imply that he would later develop an electric car for the Duryea Motor Wagon Company.
c. indicate that the quality of automobiles being developed in Europe was very poor at the time.
d. suggest that the kind of car he drove is what helped him win the race.
e. help the reader understand the differences between two-cylinder vehicles and electric automobiles.
"""
# split the mineruparsed data into csvs and save it into output_csv

# 卷型相关的正则（trigger / 题目行 / 范围声明行）统一定义在 exam_formats.py。

# enforce passing in expected_end_num
def split_into_items(lines, detect_start, expected_start_num, expected_end_num):
    """把若干行切成「编号严格连续」的一条条 item（题目 / 答案共用）。

    FSM：维护下一个期望号 expected（从 expected_start_num 起逐一递增）。某行
    只有在 detect_start(line) == expected（且不超过 expected_end_num）时才算新
    item 起点，并令 expected += 1；否则并入当前 item。这样保证 item 号严格
    1,2,3,… 连续，把正文里题号对不上的编号行（答案解析里引用的 "7."、子问题
    列表、题干内编号等）挡在外面。首个 item 起点之前的行被丢弃。
    expected_end_num 为 None 表示不设上界。返回 [(key, [lines]), ...]。
    """
    items = []  # [(key, [lines])]
    expected = expected_start_num
    for line in lines:
        key = detect_start(line)
        if key == expected and (expected_end_num is None or expected <= expected_end_num):
            items.append((key, [line]))
            expected += 1
        elif items:
            items[-1][1].append(line)
    return items


class QuestionMainbodyFSM:
    """逐行扫描 questions mainbody，直接产出一道道单题（passage 随题冗余）。

    把原来分两步的逻辑合进一个有状态机：
    - 切 span（原 _2）：questions_span_trigger_res（一组 trigger，命中任一）是
      span 的显式起点（praxis 的 "Use the following passage…" 行；plt 的
      "## Case History N" / "## Discrete Multiple-Choice Questions" 节标题）；之后所有行都留在
      当前 span 里直到下一个 trigger。范围声明行（question_range_re，praxis
      的 trigger 行本身 / plt 的 Directions 行）声明 [a, b]，把「下一个 span
      的首题号」推到 b+1；题号 == 该首题号的题目行意味着上一个 span 结束、
      一道无 trigger 的独立题开新 span（正常不触发，触发则打 WARNING）。
    - span 内分题（原 _3）：每关闭一个 span，用「全局连续题号」识别其中各题
      的起始行（parse_item），首题之前的行即该 span 的 passage，passage 随
      每道题冗余写出。两个计数器在 span 边界处相等，互不影响。

    输入是 get_questions_mainbody 产出的已裁剪主体：无前言、无答案区。
    """

    def __init__(self, exam_format: ExamFormat = PRAXIS_READING, debug: bool = True):
        self.exam_format = exam_format
        self.debug = debug
        self.separator = '=' * 100
        self.next_span_first_question = 1  # 下一个 span 的首题号（随 range 行推进）
        self.next_question_number = 1      # 全局连续题号（随每道题推进）
        self.started = False               # 是否已开过 span（无-trigger 独立题的 WARNING 判据）
        self.individual_questions = []     # 产出 [(qnum, passage, question_text)]

    def _is_span_start(self, line):
        """span 的两种起点：trigger 行（命中任一 trigger），或题号 == 下一 span
        首题号的无-trigger 独立题。"""
        if self.exam_format.matches_span_trigger(line):
            return True
        return question_number_safe_search(self.exam_format, line) == self.next_span_first_question

    def _apply_range(self, line):
        """范围声明行（praxis 的 trigger 行本身 / plt 的 span 内 Directions 行）
        把下一 span 首题号推到 b+1。"""
        range_match = self.exam_format.question_range_re.search(line)
        if not range_match:
            return
        first_q = int(range_match.group(1))
        last_q = int(range_match.group(2) or range_match.group(1))
        if first_q != self.next_span_first_question:
            print(f'WARNING: range line declares questions {first_q}…{last_q} '
                  f'but the next span should start at question {self.next_span_first_question}')
            raise ValueError(line)
        self.next_span_first_question = last_q + 1

    def _consume(self, lines, i):
        """从 span 起点 i 吃到下一个 span 起点 / EOF，沿途处理 range 行。
        返回 (span 的行列表, 下一个待处理下标)。"""
        span = [lines[i]]
        self._apply_range(lines[i])
        i += 1
        while i < len(lines) and not self._is_span_start(lines[i]):
            span.append(lines[i])
            self._apply_range(lines[i])
            i += 1
        return span, i

    def _emit_span(self, span_lines):
        """span 关闭：非空则（可选 debug 打印后）拆成单题。"""
        text = '\n'.join(span_lines).strip()
        if not text:
            return
        if self.debug:
            print(self.separator)
            print(text)
        self._parse_span_into_questions(text)

    def _parse_span_into_questions(self, span_text):
        """span 内分出 passage 和各题（原 _3._split_span_into_questions）。

        一行只有在「匹配 question_line_re 且题号 == next_question_number
        （全局连续）」时才算题目起始——span 内题号对不上的编号列表（plt 的
        Goals 1.–4.、题干里的子问题）留在 passage/题干里。
        """
        lines = span_text.splitlines()
        # 先把 passage 单独抽出来：首题之前的所有行（首题一旦出现，后续行都归题目）
        first_question_idx = next(
            (i for i, line in enumerate(lines)
             if question_number_safe_search(self.exam_format, line) == self.next_question_number),
            len(lines))
        passage = '\n'.join(lines[:first_question_idx]).rstrip()

        # 再在首题及其后的行上分题：题号从全局连续计数起严格递增（FSM 内判定），
        # 上界开放（一个 span 的题数不预先知道）
        items = split_into_items(
            lines[first_question_idx:],
            lambda line: question_number_safe_search(self.exam_format, line),
            expected_start_num=self.next_question_number,
            expected_end_num=self.next_span_first_question - 1,
        )
        for qnum, qlines in items:
            self.individual_questions.append(
                (qnum, passage, '\n'.join(qlines).strip()))
        self.next_question_number += len(items)  # 跨 span 推进全局题号

    def _parse_till_span_finish(self, lines, i):
        """passage-question span：从 trigger 行起，吃完整个 span（passage + 其各题）。"""
        self.started = True
        span, i = self._consume(lines, i)
        self._emit_span(span)
        return i

    def _parse_till_item_finish(self, lines, i):
        """无 passage 的独立题：从题目行起，吃完这一道题。"""
        if self.started:
            print(f'WARNING: question {self.next_span_first_question} appeared '
                  f'without a preceding trigger line — if it has a '
                  f'passage, the passage stayed in the previous span')
        self.started = True
        self.next_span_first_question += 1
        # 独立题内不会出现 range 行：praxis 的 range 行就是 trigger（会被
        # _is_span_start 先终止本 span）；plt 的 "Directions:" 行必跟在
        # Case History/Discrete trigger 之后，不会落在无-trigger 的独立题里。
        # 因此 _consume 沿途的 _apply_range 必是 no-op，不会推进首题号——断言之。
        before = self.next_span_first_question
        span, i = self._consume(lines, i)
        assert self.next_span_first_question == before, (
            f'independent question span unexpectedly contained a range line: {span!r}')
        self._emit_span(span)
        return i

    def parse(self, md_text):
        lines = md_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if self.exam_format.matches_span_trigger(line):
                # passage-question span 起点
                i = self._parse_till_span_finish(lines, i)
            elif question_number_safe_search(self.exam_format, line) == self.next_span_first_question:
                # 无 passage 的独立题起点
                i = self._parse_till_item_finish(lines, i)
            else:
                # 既非 trigger 也非独立题起点——只可能是首个 span 之前的杂行。
                # mainbody 已被 _1 裁剪到首个 span 起点，正常不会走到这里
                # （range 行要么是 trigger=进入 span，要么在 span 内被 _consume 吞掉），
                # 跳过即可。
                i += 1
        print(f'FSM parsed {len(self.individual_questions)} questions '
              f'(1..{self.next_question_number - 1})')
        return self.individual_questions


class SplitQuestionMainbodyIntoIndividualQuestionsStage(Stage):
    # …/{dataset}/outputs/questions_mainbody.md -> …/{dataset}/outputs/individual_questions.csv
    output_basename = individual_question_output_csv_basename

    def _produce(self, output_path, current_questions_mainbody_md):
        with open(current_questions_mainbody_md) as f:
            md_text = f.read()
        questions = QuestionMainbodyFSM(self.exam_format).parse(md_text)
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=output_csv_columns)
            writer.writeheader()
            for qnum, passage, question in questions:
                writer.writerow(asdict(IndividualQuestionRow(
                    question_number=str(qnum),
                    passage=passage,
                    question=question,
                    # 题目侧没有截图路径来源，恒取默认值（原 _3 同此）
                    original_page_screenshot_paths='[]',
                )))
        print(f'wrote {len(questions)} questions to {output_path}')

if __name__ == '__main__':
    # 从 fixture 的输入 md 沿 _1_ 的 derive 推出 questions_mainbody.md
    SplitQuestionMainbodyIntoIndividualQuestionsStage().run(
        GetQuestionsMainbodyStage().derive_output_path(mineruparsed))
