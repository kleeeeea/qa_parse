import csv
import os
import re
from re import Match

from tests.fixture._constants import mineruparsed
questionspan_output_csv = f'{os.environ['HOME']}/klee_code/git_repos/parse_evaluation/praxis_reading_1/outputs/question_spans.csv'
output_csv_columns = ['spans']
original_page_screenshot_path_root = f'{os.environ['HOME']}/klee_code/git_repos/parse_evaluation/splited'
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

SPAN_TRIGGER_RE = re.compile(r'^\s*Use the following passage', re.IGNORECASE)
# text_level=1 items that should stay inside a span (xpassage/source sub-labels)
IN_SPAN_TOP_LEVEL_RE = re.compile(r'^\s*(Passage|Source)\s+\d+\s*$', re.IGNORECASE)
# Top-level markdown headers — used as section boundaries unless the header
# text itself is a Passage/Source sub-label.
TOP_LEVEL_HEADER_RE = re.compile(r'^#\s+(.*)$')
# A top-level header that contains this phrase marks the start of the answer
# key — no more problems can appear after it, so we stop walking the file.
END_OF_PROBLEMS_RE = re.compile(r'Answers and Explanations', re.IGNORECASE)


def _split_markdown_into_spans_history(md_text):
    """Walk the markdown line by line.

    A new span begins at any line matching SPAN_TRIGGER_RE. The current span
    ends either:
      - at the start of the next trigger, or
      - at a top-level markdown header (`# ...`) whose text is NOT a
        Passage/Source sub-label (those stay inside the span).

    Lines before the first trigger (cover page, "Time: 85 Minutes", etc.) are
    discarded.
    """
    spans = []
    current_lines = None
    for line in md_text.splitlines():
        header_match = TOP_LEVEL_HEADER_RE.match(line)
        # The "Answers and Explanations" header marks the end of all problems
        # for this test — and any later top-level section (Writing Test, Math
        # Test, …) is not a problem section either, so we stop entirely.
        # Example line that triggers this:
        #   '# Praxis® Core Academic Skills for Educators: Reading Practice Test 1 Answers and Explanations'
        if header_match and END_OF_PROBLEMS_RE.search(header_match.group(1)):
            if current_lines is not None:
                spans.append('\n'.join(current_lines).strip())
                current_lines = None
            break
        if SPAN_TRIGGER_RE.match(line):
            if current_lines is not None:
                spans.append('\n'.join(current_lines).strip())
            current_lines = [line]
            continue
        if current_lines is None:
            continue
        if header_match and not IN_SPAN_TOP_LEVEL_RE.match(header_match.group(1)):
            # New top-level section — close the current span and stop collecting
            # until the next trigger.
            spans.append('\n'.join(current_lines).strip())
            current_lines = None
            continue
        current_lines.append(line)
    if current_lines is not None:
        spans.append('\n'.join(current_lines).strip())
    return [s for s in spans if s]

# Question lines are numbered with a dot ("1. Which of the following…").
# Passage line-number margins ("5 Massachusetts, and, after…") have no dot,
# so they can never match.
QUESTION_LINE_RE = re.compile(r'^\s*(\d+)\.\s')
# Declared question range on a trigger line:
#   'Use the following passage to answer questions 50 through 53.'
#   'Use the following passage to answer questions 1 and 2.'
#   'Use the following passage to answer question 6.'
TRIGGER_QUESTION_RANGE_RE = re.compile(
    r'questions?\s+(\d+)(?:\s+(?:and|through)\s+(\d+))?', re.IGNORECASE)


def _split_markdown_into_spans(md_text, debug=True):
    """FSM over lines; a span starts only at a trigger line.

    The single place a span can start is a SPAN_TRIGGER line ("Use the
    following passage…"). The trigger also declares which questions belong
    to the span ('… questions 50 through 53.'), parsed into `span_last_q`.
    Every later line — passage, questions, options, wrapped option text
    (mineru splits long options across paragraphs, e.g. Q51's option e) —
    simply stays in the current span until the next trigger, so no pending
    buffer is needed.

    `expected` holds the next question number we are looking for; a line is a
    question only if it matches "N. " with N == expected, so stray numbers
    inside passages cannot count as questions. When question `expected`
    arrives:
      - with no current span (no trigger seen), start a new span at the
        question line itself;
      - with a current span, the declared range arbitrates: N <= span_last_q
        (e.g. 52 within 50–53) is the expected case and the question stays in
        the span even if a paragraph preceded it; N > span_last_q means the
        trigger of the next span was missed in parsing — warn.

    Lines before the first trigger (cover page, Directions, …) and top-level
    `# …` headers (except Passage/Source sub-labels) are discarded.
    Terminates at the "Answers and Explanations" top-level header, e.g.
    '# Praxis® Core Academic Skills for Educators: Reading Practice Test 1 Answers and Explanations'
    """
    spans = []
    current = None     # lines of the span being built
    next_question_number = 1       # next question number we are looking for
    span_last_q = None # last question number declared by the current trigger

    def close_current():
        nonlocal current
        if current is not None:
            text = '\n'.join(current).strip()
            if text:
                spans.append(text)
                if debug:
                    print(separator)
                    print(text)
        current = None
    separator = '=' * 100
    for line in md_text.splitlines():
        header_match = TOP_LEVEL_HEADER_RE.match(line)
        if header_match and not IN_SPAN_TOP_LEVEL_RE.match(header_match.group(1)):
            if END_OF_PROBLEMS_RE.search(header_match.group(1)):
                close_current()
                break
            # Cover-page / section header — span boundary, discard the header.
            close_current()
            continue
        if is_reading_material_start(line):
            # The single place a new span starts.
            close_current()
            current = [line]
            range_match = TRIGGER_QUESTION_RANGE_RE.search(line)
            span_last_q = int(range_match.group(2) or range_match.group(1)) if range_match else None
            continue
        question_match = QUESTION_LINE_RE.match(line)
        if question_match and int(question_match.group(1)) == next_question_number:
            if current is None:
                # Question with no preceding passage/trigger — start a new
                # span at the question line itself.
                current = []
                span_last_q = None
            elif span_last_q is not None and next_question_number > span_last_q:
                print(f'WARNING: question {next_question_number} exceeds declared range '
                      f'(…{span_last_q}) of the current span — missed a trigger line?')
            next_question_number += 1
            current.append(line)
            continue
        if current is not None:
            current.append(line)
    close_current()
    print(f'FSM saw questions 1..{next_question_number - 1} in {len(spans)} spans')
    return spans


def is_reading_material_start(l) -> re.Match[str] | None:
    return SPAN_TRIGGER_RE.match(l)


def split_mineru_parsed_md_into_consecutive_problem_spans(current_mineruparsed):
    with open(current_mineruparsed) as f:
        md_text = f.read()
    spans = _split_markdown_into_spans(md_text)
    out_dir = os.path.dirname(questionspan_output_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(questionspan_output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(output_csv_columns)
        for span_text in spans:
            writer.writerow([span_text])
    print(f'wrote {len(spans)} spans to {questionspan_output_csv}')


if __name__ == '__main__':
    split_mineru_parsed_md_into_consecutive_problem_spans(mineruparsed)
