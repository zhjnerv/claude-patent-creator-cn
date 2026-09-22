"""中国专利范本的目标 IPC、候选 IPC 和加权选择门禁。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cn-patent-application-creator" / "scripts"
RANKER = SCRIPTS / "rank_template_candidates.py"
GATE = SCRIPTS / "check_stage_gate.py"


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_ipc_normalization_accepts_epo_ipcr_text_suffixes():
    ranker = _module(RANKER, "cn_template_ipc_normalization_test")
    assert ranker.normalize_ipc("G06F 11/36 (2006.01)") == "G06F11/36"
    assert ranker.normalize_ipc("G06F 11/36 A I") == "G06F11/36"
    assert ranker.normalize_ipc("H04M 1/72406") == "H04M1/72406"


def test_ipc_similarity_hierarchy_and_weight_can_change_recommendation():
    ranker = _module(RANKER, "cn_template_ipc_ranker_test")
    search = {
        "schema_id": "cn-patent-template-search/v1",
        "target_ipc": {
            "status": "determined",
            "ipc_codes": ["G06F11/36"],
            "source": "technical_features_explicit",
        },
    }
    candidates = {
        "schema_id": "cn-patent-template-candidates/v1",
        "candidates": [
            {
                "publication_number": "CN-A",
                "title": "高文本相关候选",
                "technical_relevance_score": 0.95,
                "technical_relevance_reason": "标题和摘要高度相关",
            },
            {
                "publication_number": "CN-B",
                "title": "IPC完全相同候选",
                "technical_relevance_score": 0.82,
                "technical_relevance_reason": "技术链相关且分类完全相同",
            },
        ],
    }

    def fake_epo(number: str):
        if number == "CN-A":
            return ["G06Q10/10"], {"provider": "epo_ops", "status": "success"}
        return ["G06F11/36"], {"provider": "epo_ops", "status": "success"}

    report = ranker.rank_templates(search, candidates, ipc_weight=0.35, resolver=fake_epo)
    assert report["selected"]["publication_number"] == "CN-B"
    assert report["selected"]["classification_source"] == "epo_ops"
    assert report["selected"]["ipc_similarity"] == {
        "score": 1.0,
        "level": "exact",
        "target_ipc": "G06F11/36",
        "candidate_ipc": "G06F11/36",
    }
    assert report["classification_policy"]["preferred_provider"] == "epo_ops"


def test_external_epo_provider_command_is_process_isolated(tmp_path):
    ranker = _module(RANKER, "cn_template_external_epo_provider_test")
    provider = tmp_path / "provider.py"
    provider.write_text(
        "import json, sys\n"
        "assert sys.argv[-1] == 'CN123A'\n"
        "print(json.dumps({'ipc_codes': ['G06F 11/36 (2006.01)']}))\n",
        encoding="utf-8",
    )
    resolver = ranker.build_epo_resolver(f'{sys.executable} {provider}')
    codes, attempt = resolver("CN123A")
    assert codes == ["G06F11/36"]
    assert attempt["provider"] == "epo_ops"
    assert attempt["status"] == "success"


def test_ranker_rejects_suggested_target_ipc_and_unresolved_candidates():
    ranker = _module(RANKER, "cn_template_ipc_ranker_reject_test")
    candidates = {
        "schema_id": "cn-patent-template-candidates/v1",
        "candidates": [{
            "publication_number": "CN-A",
            "title": "候选",
            "technical_relevance_score": 0.9,
            "technical_relevance_reason": "相关",
        }],
    }
    with pytest.raises(ranker.SelectionError, match="目标 IPC 尚未确定"):
        ranker.rank_templates(
            {"schema_id": "cn-patent-template-search/v1", "target_ipc": {
                "status": "suggested", "ipc_codes": ["G06F"], "source": "mapping"
            }},
            candidates,
            resolver=lambda _number: ([], {"provider": "epo_ops", "status": "unavailable"}),
        )

    with pytest.raises(ranker.SelectionError, match="所有范本候选的 IPC 均未取得"):
        ranker.rank_templates(
            {"schema_id": "cn-patent-template-search/v1", "target_ipc": {
                "status": "determined", "ipc_codes": ["G06F11/36"], "source": "explicit"
            }},
            candidates,
            resolver=lambda _number: ([], {"provider": "epo_ops", "status": "unavailable"}),
        )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _gate_fixture(tmp_path: Path) -> tuple[Path, Path]:
    search = tmp_path / "search-query.json"
    candidates = tmp_path / "template-candidates.json"
    selection = tmp_path / "template-selection.json"
    guide = tmp_path / "template-style-guide.json"
    brief = tmp_path / "style-brief.json"
    ledger = tmp_path / "feature-ledger.json"
    state = tmp_path / "stage2-gate.json"
    output = tmp_path / "stage2-gate-report.json"

    _write_json(search, {
        "schema_id": "cn-patent-template-search/v1",
        "target_ipc": {"status": "determined", "ipc_codes": ["G06F11/36"], "source": "technical_features_explicit"},
    })
    _write_json(candidates, {
        "schema_id": "cn-patent-template-candidates/v1",
        "candidates": [{
            "publication_number": "CN100A", "title": "范本", "technical_relevance_score": 0.9,
            "technical_relevance_reason": "同领域", "ipc_codes": ["G06F11/36"]
        }],
    })
    _write_json(selection, {
        "schema_id": "cn-patent-template-selection/v1",
        "target_ipc": {"status": "determined", "ipc_codes": ["G06F11/36"], "source": "technical_features_explicit"},
        "weights": {"technical_relevance": 0.65, "ipc_similarity": 0.35},
        "classification_policy": {"preferred_provider": "epo_ops", "fallback_order": ["candidate_input"]},
        "candidates": [{
            "publication_number": "CN100A", "technical_relevance_score": 0.9,
            "technical_relevance_reason": "同领域", "ipc_status": "resolved", "ipc_codes": ["G06F11/36"],
            "classification_source": "candidate_input", "eligible": True,
            "classification_attempts": [{"provider": "epo_ops", "status": "unavailable"}],
            "ipc_similarity": {"score": 1.0, "level": "exact", "target_ipc": "G06F11/36", "candidate_ipc": "G06F11/36"},
            "weighted_score": 0.935,
        }],
        "recommended": {"publication_number": "CN100A", "weighted_score": 0.935},
        "selected": {"publication_number": "CN100A", "weighted_score": 0.935, "ipc_codes": ["G06F11/36"], "ipc_similarity": {"score": 1.0, "level": "exact"}, "classification_source": "candidate_input", "override_recommended": False, "selection_reason": "加权最高"},
        "inputs": {
            "search_query_path": str(search), "search_query_sha256": hashlib.sha256(search.read_bytes()).hexdigest(),
            "candidate_manifest_path": str(candidates), "candidate_manifest_sha256": hashlib.sha256(candidates.read_bytes()).hexdigest(),
        },
    })
    _write_json(guide, {"template_patent": "CN100A"})
    _write_json(brief, {
        "schema_id": "cn-patent-style-brief/v1", "source": {"mode": "template"},
        "specification": {"embodiments": {"organization": "single_flow"}}, "warnings": []
    })
    _write_json(ledger, {
        "schema_id": "cn-patent-feature-ledger/v2",
        "features": [{"feature_id": "F001", "classification": "distinguishing"}],
    })
    _write_json(state, {
        "schema_id": "cn-patent-stage2-gate/v2", "case_id": "case",
        "cnipa_manual_search": {"status": "not_completed", "user_authorization": {"user_quote": "明确授权继续", "granted_at": "2026-08-27"}},
        "template_selection": {
            "status": "confirmed", "style_guides": [guide.name],
            "search_query_path": search.name, "candidate_manifest_path": candidates.name,
            "selection_report_path": selection.name,
            "user_authorization": {"user_quote": "明确选择该范本", "granted_at": "2026-08-27"},
        },
        "style_brief_path": brief.name, "feature_ledger_path": ledger.name,
    })
    return state, output


def test_stage_gate_v2_accepts_bound_ipc_selection(tmp_path):
    state, output = _gate_fixture(tmp_path)
    result = _run(GATE, "--state", str(state), "--workspace", str(tmp_path), "--output", str(output))
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["decision"] == "CLEARED"
    assert any(note["gate_id"] == "GATE-IPC-013" for note in report["notes"])


def test_stage_gate_v2_blocks_stale_candidate_manifest(tmp_path):
    state, output = _gate_fixture(tmp_path)
    candidates = tmp_path / "template-candidates.json"
    payload = json.loads(candidates.read_text(encoding="utf-8"))
    payload["candidates"][0]["title"] = "已变化"
    _write_json(candidates, payload)
    result = _run(GATE, "--state", str(state), "--workspace", str(tmp_path), "--output", str(output))
    assert result.returncode == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert any(block["gate_id"] == "GATE-IPC-003" for block in report["blocks"])


def test_stage_gate_v2_recomputes_scores_and_requires_epo_first(tmp_path):
    state, output = _gate_fixture(tmp_path)
    selection_path = tmp_path / "template-selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection["candidates"][0]["weighted_score"] = 0.1
    selection["candidates"][0]["classification_attempts"] = [
        {"provider": "candidate_input", "status": "success"}
    ]
    _write_json(selection_path, selection)
    result = _run(GATE, "--state", str(state), "--workspace", str(tmp_path), "--output", str(output))
    assert result.returncode == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    gate_ids = {block["gate_id"] for block in report["blocks"]}
    assert "GATE-IPC-009" in gate_ids
    assert "GATE-IPC-010" in gate_ids


def test_new_ipc_contract_schemas_are_utf8_json():
    references = ROOT / "skills" / "cn-patent-application-creator" / "references"
    expectations = {
        "template-candidates-schema.json": "cn-patent-template-candidates/v1",
        "template-selection-schema.json": "cn-patent-template-selection/v1",
        "stage2-gate-schema-v2.json": "cn-patent-stage2-gate/v2",
        "claim-architecture-schema-v1.json": "cn-patent-claim-architecture/v1",
    }
    for name, schema_id in expectations.items():
        raw = (references / name).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert json.loads(raw.decode("utf-8"))["$id"] == schema_id


def test_stage_gate_accepts_concise_verbatim_user_authorization(tmp_path):
    """“同意”“是”等简短原话仍是有效授权，不得由字符数门槛否定。"""
    import importlib.util

    script = ROOT / "skills/cn-patent-application-creator/scripts/check_stage_gate.py"
    spec = importlib.util.spec_from_file_location("stage_gate_concise_quote", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.require_authorization(
        {"user_quote": "同意", "granted_at": "2026-09-08"}, "范本确认"
    ) == "同意"

def test_stage_gate_pending_template_is_cleared_with_pending(tmp_path):
    state, output = _gate_fixture(tmp_path)
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    state_payload["template_selection"]["status"] = "pending"
    _write_json(state, state_payload)

    # Also update style-brief.json to match "pending" template selection
    brief_path = tmp_path / "style-brief.json"
    brief_payload = json.loads(brief_path.read_text(encoding="utf-8"))
    brief_payload["source"]["mode"] = "default"
    _write_json(brief_path, brief_payload)

    result = _run(GATE, "--state", str(state), "--workspace", str(tmp_path), "--output", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["decision"] == "CLEARED_WITH_PENDING"
    assert any(p["key"] == "template.selection_pending" for p in report["pending_decisions"])

def test_stage_gate_search_not_completed_no_quote_is_cleared_with_pending(tmp_path):
    state, output = _gate_fixture(tmp_path)
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    state_payload["cnipa_manual_search"]["status"] = "not_completed"
    state_payload["cnipa_manual_search"].pop("user_authorization", None)
    _write_json(state, state_payload)
    result = _run(GATE, "--state", str(state), "--workspace", str(tmp_path), "--output", str(output))
    assert result.returncode == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["decision"] == "CLEARED_WITH_PENDING"
    assert any(p["key"] == "search.cnipa_manual_search_pending_authorization" for p in report["pending_decisions"])

def test_stage_gate_search_not_completed_with_quote_is_cleared_no_pending(tmp_path):
    state, output = _gate_fixture(tmp_path)
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    state_payload["cnipa_manual_search"]["status"] = "not_completed"
    state_payload["cnipa_manual_search"]["user_authorization"] = {"user_quote": "同意", "granted_at": "2026-09-22"}
    _write_json(state, state_payload)
    result = _run(GATE, "--state", str(state), "--workspace", str(tmp_path), "--output", str(output))
    assert result.returncode == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["decision"] == "CLEARED"
    assert not any(p["key"] == "search.cnipa_manual_search_pending_authorization" for p in report.get("pending_decisions", []))
