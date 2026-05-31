from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "docs" / "orchestration-boundary.md"
README = ROOT / "README.md"
INTEGRATION = ROOT / "docs" / "integration.md"
MQ_AGENT_PROFILE = ROOT / "profiles" / "mq-agent.json"


def test_orchestration_boundary_doc_exists():
    assert BOUNDARY.exists(), "docs/orchestration-boundary.md missing"


def test_boundary_doc_names_repo_roles_and_approval_rules():
    text = BOUNDARY.read_text(encoding="utf-8")

    for name in ("mq-mcp", "mq-agent", "mq-hal", "repo-signal", "mq-image-analyze"):
        assert name in text

    for phrase in (
        "Class A",
        "Class B",
        "Class C",
        "Class D",
        "Approval required",
        "Agent Decision Rules",
    ):
        assert phrase in text


def test_public_docs_link_to_boundary():
    assert "docs/orchestration-boundary.md" in README.read_text(encoding="utf-8")
    assert "docs/orchestration-boundary.md" in INTEGRATION.read_text(encoding="utf-8")


def test_mq_agent_profile_declares_boundary_limits():
    text = MQ_AGENT_PROFILE.read_text(encoding="utf-8")

    assert "validate_orchestration_contract" in text
    assert "Class C/D tools must remain approval-gated" in text
    assert "must not reimplement mq-mcp review logic" in text
