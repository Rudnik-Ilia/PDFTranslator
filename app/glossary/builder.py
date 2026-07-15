import csv
from pathlib import Path


def write_glossary_csv(path: Path, terms: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["source_term", "target_term", "type", "confidence", "approved"])
        writer.writeheader()
        for term in terms:
            writer.writerow({"source_term": term, "target_term": "", "type": "candidate", "confidence": "0.30", "approved": "false"})
