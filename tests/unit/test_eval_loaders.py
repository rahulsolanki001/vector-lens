"""
Unit tests for eval dataset loaders.
"""

from __future__ import annotations

import pytest

from vlens.eval.loaders import CSVLoader


@pytest.mark.unit
def test_csv_loader_loads_json_vectors_and_relevant_ids(tmp_path) -> None:
    dataset_path = tmp_path / "queries.csv"
    dataset_path.write_text(
        "\n".join(
            [
                "query_id,query,vector,relevant_ids",
                'q1,portfolio risk,"[0.1, 0.2, 0.3]","[""doc1"", ""doc2""]"',
            ]
        )
    )

    dataset = CSVLoader().load(dataset_path)

    assert dataset.name == "queries"
    assert dataset.query_count == 1
    assert dataset.relevant_doc_count == 2
    assert dataset.queries[0].id == "q1"
    assert dataset.queries[0].text == "portfolio risk"
    assert dataset.queries[0].vector == [0.1, 0.2, 0.3]
    assert dataset.queries[0].relevant_ids == {"doc1", "doc2"}


@pytest.mark.unit
def test_csv_loader_supports_column_aliases_and_delimited_values(tmp_path) -> None:
    dataset_path = tmp_path / "alias.csv"
    dataset_path.write_text(
        "\n".join(
            [
                "qid,text,embedding,expected_ids",
                "q1,query one,0.1 0.2 0.3,doc1|doc2|doc3",
                'q2,query two,"0.4,0.5,0.6","doc4, doc5"',
            ]
        )
    )

    dataset = CSVLoader().load(dataset_path)

    assert dataset.query_count == 2
    assert dataset.queries[0].vector == [0.1, 0.2, 0.3]
    assert dataset.queries[0].relevant_ids == {"doc1", "doc2", "doc3"}
    assert dataset.queries[1].vector == [0.4, 0.5, 0.6]
    assert dataset.queries[1].relevant_ids == {"doc4", "doc5"}


@pytest.mark.unit
def test_csv_loader_rejects_missing_required_column(tmp_path) -> None:
    dataset_path = tmp_path / "missing-column.csv"
    dataset_path.write_text("query_id,query,vector\nq1,text,0.1 0.2")

    with pytest.raises(ValueError, match="missing required column"):
        CSVLoader().load(dataset_path)


@pytest.mark.unit
def test_csv_loader_rejects_missing_text_value(tmp_path) -> None:
    dataset_path = tmp_path / "missing-text.csv"
    dataset_path.write_text("query_id,query,vector,relevant_ids\nq1,,0.1 0.2,doc1")

    with pytest.raises(ValueError, match=r"row 2.*query"):
        CSVLoader().load(dataset_path)


@pytest.mark.unit
def test_csv_loader_rejects_non_numeric_vector(tmp_path) -> None:
    dataset_path = tmp_path / "bad-vector.csv"
    dataset_path.write_text("query_id,query,vector,relevant_ids\nq1,text,0.1 nope,doc1")

    with pytest.raises(ValueError, match="not numeric"):
        CSVLoader().load(dataset_path)


@pytest.mark.unit
def test_csv_loader_rejects_empty_dataset(tmp_path) -> None:
    dataset_path = tmp_path / "empty.csv"
    dataset_path.write_text("query_id,query,vector,relevant_ids\n")

    with pytest.raises(ValueError, match="contains no query rows"):
        CSVLoader().load(dataset_path)
