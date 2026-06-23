# Parse Evaluation Pipeline

Run the full parser from this directory:

```bash
/Users/l/miniconda3/envs/base124/bin/python _overall_pipeline.py QUESTION_FULL_MD ANSWER_FULL_MD
```

`QUESTION_FULL_MD` and `ANSWER_FULL_MD` are MinerU parsed markdown files,
usually named `full.md`. The pipeline writes outputs next to the input files:

- `questions_mainbody.md` next to the question markdown
- `individual_questions.csv` next to the question markdown
- `answer_spans.csv` next to the answer markdown
- `problems_and_answers.csv` next to the question markdown

The exam format is inferred from the question input path. Override it when
needed:

```bash
/Users/l/miniconda3/envs/base124/bin/python _overall_pipeline.py QUESTION_FULL_MD ANSWER_FULL_MD --exam-format plt
```

Existing outputs are skipped by default. Use `--force` to recreate them:

```bash
/Users/l/miniconda3/envs/base124/bin/python _overall_pipeline.py QUESTION_FULL_MD ANSWER_FULL_MD --force
```

Running without positional arguments uses the bundled fixture inputs.
