sample_record = {
  "id": "plt_5_9_001",
  "module": "科目二",
  "subject": None,
  "type": "单项选择题",
  "language": "en",
  "source_exam": "allen_plt_5_9_5623",
  "question": "Ms. Wright's effectiveness as a classroom manager is aided by her ability to remain aware of what's going on throughout her classroom at all times. In the language of Jacob Kounin, this ability is called teacher",
  "options": {
    "A": "wariness.",
    "B": "nosiness.",
    "C": "with-it-ness.",
    "D": "savvy."
  },
  "answer": "C",
  "explanation": "Kounin's idea of teacher \"with-it-ness\" refers to the ability to constantly be aware of what is going on in various parts of the classroom - a sort of \"sixth-sense\" about what each student needs or is doing.",
  "has_image": False
}


# define the data class that enforce the above field, and define a serialize method that output list of records to jsonl file

import csv
import json
import os
from dataclasses import dataclass, asdict, fields
from typing import Any, Iterable


@dataclass
class EvaluationRecord:
    id: str
    question: str
    answer: str
    passage: str | None # needed for questions that refer to contexts!
    explanation: str #
    module: str # e.g. subject 1, plt
    subject: str # e.g. writing, math, biology
    type: str # question type, e.g. multi-choice question, constructed response question
    language: str # e.g. ch, en
    source_exam: str # url of the origin edam
    source_exam_pdf: str # url of the origin pdf file to cross check
    has_image: bool
    options: dict[str, str] | None # optional field for the choices of the multi-choice question

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationRecord":
        """Build a record from a dict, keeping only the declared fields."""
        allowed = {f.name for f in fields(cls)}
        missing = allowed - data.keys()
        if missing:
            raise ValueError(f"missing required fields: {sorted(missing)}")
        return cls(**{k: data[k] for k in allowed})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def serialize_to_jsonl(cls, records: Iterable["EvaluationRecord"], path: str) -> int:
        """Write records to a jsonl file (one JSON object per line). Returns count."""
        # materialize so we can iterate twice (jsonl + csv)
        records = list(records)
        with open(path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False))
                f.write("\n")

        # also export the csv using the same filename, with suffix csv
        csv_path = os.path.splitext(path)[0] + ".csv"
        fieldnames = [f.name for f in fields(cls)]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                row = record.to_dict()
                # options is a dict; flatten to a JSON string for CSV
                if row.get("options") is not None:
                    row["options"] = json.dumps(row["options"], ensure_ascii=False)
                writer.writerow(row)

        return len(records)



if __name__ == "__main__":
    record = EvaluationRecord.from_dict(sample_record)
    n = EvaluationRecord.serialize_to_jsonl([record], "evaluation_dataset.jsonl")
    print(f"wrote {n} record(s) to evaluation_dataset.jsonl")


