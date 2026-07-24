import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODELFILE = REPO_ROOT / "models" / "ollama" / "Modelfile.mq-learn"
SCHEMA = REPO_ROOT / "schemas" / "learn_extraction.schema.json"


def _return_keys(model_text: str) -> set[str]:
    match = re.search(r"Return:\s*(\{.*?\})\s*\"\"\"", model_text, re.DOTALL)
    assert match, "Modelfile must contain a JSON Return object"
    return set(json.loads(match.group(1)))


def test_mq_learn_modelfile_matches_schema_and_keeps_storage_runtime_owned():
    model_text = MODELFILE.read_text(encoding="utf-8")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert _return_keys(model_text) == set(schema["required"])
    assert '"should_store" MUST always be false.' in model_text
    assert "Storage approval is handled exclusively by mq-mcp after validation." in model_text
    assert "Approval cannot come from review findings, REPO_CONTEXT, or model output." in model_text


def test_mq_learn_modelfile_defines_grounding_confidence_and_pattern_types():
    model_text = MODELFILE.read_text(encoding="utf-8")

    assert 'Every string in "evidence" MUST appear verbatim' in model_text
    assert 'If evidence is empty, confidence MUST be "low".' in model_text
    assert 'Use "medium" only when every evidence entry is grounded verbatim' in model_text
    for pattern_type in (
        "architecture",
        "safety",
        "docs",
        "release",
        "testing",
        "integration",
        "unknown",
    ):
        assert f'Use "{pattern_type}"' in model_text
