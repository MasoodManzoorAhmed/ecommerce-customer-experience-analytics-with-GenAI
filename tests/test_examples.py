"""Step c examples: valid SQL, and no leakage of evaluation answers into the prompt."""

import json
import re

import pytest

from genai.text_to_sql.eval_set import ALLOWED_TABLES, EXPECTED_PATH, load_eval_set, tables_used
from genai.text_to_sql.evaluate import results_match
from genai.text_to_sql.guardrails import check_sql, run_safely
from genai.text_to_sql.retriever import load_examples
from src.db import DB_PATH

EXAMPLES = load_examples()
EVAL = load_eval_set()
needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="database not built")


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def test_examples_are_unique_and_use_allowed_tables():
    questions = [e.question for e in EXAMPLES]
    assert len(set(questions)) == len(questions)
    for ex in EXAMPLES:
        assert tables_used(ex.sql) <= ALLOWED_TABLES, ex.question
        check_sql(ex.sql)  # passes the same guardrails as model output


def test_no_example_question_is_a_near_copy_of_an_evaluation_question():
    for ex in EXAMPLES:
        for item in EVAL:
            a, b = words(ex.question), words(item.question)
            overlap = len(a & b) / len(a | b)
            assert overlap < 0.7, f"'{ex.question}' is too close to {item.id}"


@needs_db
def test_no_example_result_equals_an_evaluation_answer():
    """If an example's result matched an exam answer, the model could copy it: leakage."""
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    for ex in EXAMPLES:
        result = run_safely(check_sql(ex.sql))
        assert result["rows"], f"example returns no rows: {ex.question}"
        for item in EVAL:
            assert not results_match(expected[item.id], result), (
                f"example '{ex.question}' gives the answer to {item.id}"
            )


def test_retriever_returns_the_most_similar_examples_first():
    pytest.importorskip("sentence_transformers")
    from genai.text_to_sql.retriever import ExampleRetriever

    try:
        retriever = ExampleRetriever(EXAMPLES)
    except OSError:
        pytest.skip("embedding model not available offline")
    top = retriever.top_k("How many sellers are in the state of Parana?", k=3)
    assert len(top) == 3
    assert top[0][0].question == "How many sellers are located in the state of Parana?"
    assert top[0][1] >= top[1][1] >= top[2][1]
