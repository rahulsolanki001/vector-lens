"""
Dataset loaders for the eval harness.

Loaders normalize different dataset formats into EvalDataset so the runner can
stay focused on querying backends and computing metrics.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EvalQuery(BaseModel):
    """One evaluation query and its relevance labels."""

    id: str
    text: str
    vector: list[float]
    relevant_ids: set[str] = Field(default_factory=set)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalDataset(BaseModel):
    """Loaded evaluation dataset."""

    name: str
    queries: list[EvalQuery] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def query_count(self) -> int:
        """Number of queries in the dataset."""
        return len(self.queries)

    @property
    def relevant_doc_count(self) -> int:
        """Number of unique relevant document IDs across all queries."""
        relevant_ids: set[str] = set()
        for query in self.queries:
            relevant_ids.update(query.relevant_ids)
        return len(relevant_ids)


class JSONLoader:
    """
    JSON / JSONL dataset loader.

    Accepts either:
      - A JSON array file:  [{id, text, vector, relevant_ids}, ...]
      - A JSONL file:       one JSON object per line (same fields)

    Field aliases mirror CSVLoader:
      id / query_id / qid
      text / query
      vector / query_vector / embedding
      relevant_ids / relevant / doc_ids / expected_ids
    """

    def load(self, path: str | Path) -> EvalDataset:
        json_path = Path(path)
        raw = json_path.read_text(encoding="utf-8").strip()

        # JSONL: lines that each start with "{"
        if raw.startswith("{"):
            records: list[dict[str, Any]] = [
                json.loads(line) for line in raw.splitlines() if line.strip()
            ]
        else:
            records = json.loads(raw)
            if not isinstance(records, list):
                raise ValueError(f"JSON dataset '{json_path}' must be an array of objects.")

        if not records:
            raise ValueError(f"JSON dataset '{json_path}' contains no records.")

        queries = [_parse_json_record(r, i + 1) for i, r in enumerate(records)]
        return EvalDataset(
            name=json_path.stem,
            queries=queries,
            metadata={"source": str(json_path), "format": "json"},
        )


class FiQALoader:
    """Planned built-in FiQA dataset loader."""

    def load(self, path: str | None = None) -> EvalDataset:
        raise NotImplementedError("FiQA loader is planned for a future release.")


class CSVLoader:
    """
    CSV dataset loader.

    Supported column aliases:
      - query ID:      id, query_id, qid
      - query text:    text, query
      - vector:        vector, query_vector, embedding
      - relevant IDs:  relevant_ids, relevant, doc_ids, expected_ids

    Relevant IDs may be JSON lists, comma-separated, pipe-separated, or
    whitespace-separated. Vectors may be JSON lists or comma/whitespace-separated
    numbers.
    """

    def load(self, path: str | Path) -> EvalDataset:
        csv_path = Path(path)
        with csv_path.open(newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"CSV dataset '{csv_path}' is missing a header row.")

            columns = _ColumnMap.from_fieldnames(reader.fieldnames)
            queries = [
                _parse_row(row, columns, row_number=index)
                for index, row in enumerate(reader, start=2)
            ]

        if not queries:
            raise ValueError(f"CSV dataset '{csv_path}' contains no query rows.")

        return EvalDataset(
            name=csv_path.stem,
            queries=queries,
            metadata={
                "source": str(csv_path),
                "format": "csv",
            },
        )


class _ColumnMap(BaseModel):
    id: str
    text: str
    vector: str
    relevant_ids: str

    @classmethod
    def from_fieldnames(cls, fieldnames: Sequence[str]) -> _ColumnMap:
        normalized = {field.lower().strip(): field for field in fieldnames}

        return cls(
            id=_pick_column(normalized, ["id", "query_id", "qid"]),
            text=_pick_column(normalized, ["text", "query"]),
            vector=_pick_column(normalized, ["vector", "query_vector", "embedding"]),
            relevant_ids=_pick_column(
                normalized,
                ["relevant_ids", "relevant", "doc_ids", "expected_ids"],
            ),
        )


def _pick_column(normalized: dict[str, str], aliases: list[str]) -> str:
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]

    raise ValueError(
        f"CSV dataset is missing required column. Expected one of: {', '.join(aliases)}."
    )


def _parse_row(row: dict[str, str], columns: _ColumnMap, row_number: int) -> EvalQuery:
    query_id = _required(row, columns.id, row_number)
    text = _required(row, columns.text, row_number)
    vector = _parse_vector(_required(row, columns.vector, row_number), row_number)
    relevant_ids = _parse_relevant_ids(
        _required(row, columns.relevant_ids, row_number),
        row_number,
    )

    if not relevant_ids:
        raise ValueError(f"CSV row {row_number} must include at least one relevant ID.")

    return EvalQuery(
        id=query_id,
        text=text,
        vector=vector,
        relevant_ids=relevant_ids,
    )


def _required(row: dict[str, str], column: str, row_number: int) -> str:
    value = row.get(column, "")
    value = value.strip() if value else ""
    if not value:
        raise ValueError(f"CSV row {row_number} is missing required '{column}' value.")
    return value


def _parse_relevant_ids(raw: str, row_number: int) -> set[str]:
    values = _parse_json_list(raw)
    if values is None:
        values = [part for part in re.split(r"[\s,|]+", raw) if part]

    relevant_ids = {str(value).strip() for value in values if str(value).strip()}
    if not relevant_ids:
        raise ValueError(f"CSV row {row_number} has no parseable relevant IDs.")

    return relevant_ids


def _parse_vector(raw: str, row_number: int) -> list[float]:
    values = _parse_json_list(raw)
    if values is None:
        values = [part for part in re.split(r"[\s,]+", raw) if part]

    if not values:
        raise ValueError(f"CSV row {row_number} has an empty query vector.")

    try:
        return [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"CSV row {row_number} contains a query vector that is not numeric."
        ) from exc


def _parse_json_record(record: dict[str, Any], record_number: int) -> EvalQuery:
    """Parse one JSON object into an EvalQuery using the same field aliases as CSV."""
    aliases = {k.lower(): v for k, v in record.items()}

    def _get(options: list[str], label: str) -> Any:
        for key in options:
            if key in aliases:
                return aliases[key]
        raise ValueError(
            f"JSON record {record_number} is missing required field. "
            f"Expected one of: {', '.join(options)}."
        )

    raw_id = str(_get(["id", "query_id", "qid"], "id"))
    raw_text = str(_get(["text", "query"], "text"))
    raw_vector = _get(["vector", "query_vector", "embedding"], "vector")
    raw_rel = _get(["relevant_ids", "relevant", "doc_ids", "expected_ids"], "relevant_ids")

    # Vector: already a list or a JSON string
    if isinstance(raw_vector, list):
        try:
            vector = [float(v) for v in raw_vector]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"JSON record {record_number} has a non-numeric vector.") from exc
    else:
        vector = _parse_vector(str(raw_vector), record_number)

    # Relevant IDs: list or delimited string
    if isinstance(raw_rel, list):
        relevant_ids = {str(v).strip() for v in raw_rel if str(v).strip()}
    else:
        relevant_ids = _parse_relevant_ids(str(raw_rel), record_number)

    if not relevant_ids:
        raise ValueError(f"JSON record {record_number} has no relevant IDs.")

    return EvalQuery(id=raw_id, text=raw_text, vector=vector, relevant_ids=relevant_ids)


def _parse_json_list(raw: str) -> list[Any] | None:
    stripped = raw.strip()
    if not stripped.startswith("["):
        return None

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, list):
        return None

    return parsed


__all__ = [
    "CSVLoader",
    "EvalDataset",
    "EvalQuery",
    "FiQALoader",
    "JSONLoader",
]
