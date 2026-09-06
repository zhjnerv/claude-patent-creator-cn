"""feature ledger v2 的数据流、方法—系统和异常路径回归。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/cn-patent-application-creator/scripts/build_feature_ledger.py"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    claims = tmp_path / "权利要求书.md"
    specification = tmp_path / "说明书.md"
    ledger = tmp_path / "feature-ledger.json"
    output = tmp_path / "feature-ledger-report.json"
    claims.write_text(
        "# 权利要求书\n\n"
        "1. 一种处理方法，包括预先配置规则，读取输入数据，输出结果并设置低置信度完成状态及原因码。\n\n"
        "9. 一种处理系统，包括规则配置模块、数据处理模块和结果存储模块，所述结果存储模块设置低置信度完成状态及原因码。\n",
        encoding="utf-8",
    )
    specification.write_text(
        "# 示例\n\n## 技术领域\n\n数据处理。\n\n## 背景技术\n\n现有技术。\n\n"
        "## 发明内容\n\n预先配置规则，读取输入数据，输出结果。\n\n## 附图说明\n\n无。\n\n"
        "## 具体实施方式\n\n预先配置规则后读取输入数据，输出结果并设置低置信度完成状态及原因码，存储结果值、置信度、状态和原因码。\n",
        encoding="utf-8",
    )
    features = [
        {
            "feature_id": "F001", "name": "预先配置规则", "statement": "预先配置规则", "classification": "distinguishing",
            "prior_art_status": {"verdict": "not_found_in_searched_outlets"}, "technical_effect": "使规则与运行处理分离",
            "evidence": [{"source": "交底书", "locator": "1"}],
            "claim_sites": [
                {"claim_number": 1, "part": "characterizing", "claim_type": "method", "execution_role": "precondition", "verbatim": "预先配置规则"},
                {"claim_number": 9, "part": "characterizing", "claim_type": "system", "execution_role": "module", "actor": "规则配置模块", "verbatim": "规则配置模块"},
            ],
            "spec_sites": [{"section": "发明内容", "anchor": "预先配置规则"}], "drawing_sites": [],
            "flow": {"action_phase": "preconfigured", "input_objects": ["规则参数"], "processing_actor": "规则配置模块", "action": "配置", "output_objects": ["规则"], "downstream_feature_ids": ["F002"], "exception_path_ids": []},
        },
        {
            "feature_id": "F002", "name": "读取输入数据", "statement": "读取输入数据", "classification": "distinguishing",
            "prior_art_status": {"verdict": "not_found_in_searched_outlets"}, "technical_effect": "取得待处理数据",
            "evidence": [{"source": "交底书", "locator": "2"}],
            "claim_sites": [
                {"claim_number": 1, "part": "characterizing", "claim_type": "method", "execution_role": "runtime_step", "verbatim": "读取输入数据"},
                {"claim_number": 9, "part": "characterizing", "claim_type": "system", "execution_role": "module", "actor": "数据处理模块", "verbatim": "数据处理模块"},
            ],
            "spec_sites": [{"section": "发明内容", "anchor": "读取输入数据"}], "drawing_sites": [],
            "flow": {"action_phase": "runtime_input", "input_objects": ["输入源"], "processing_actor": "数据处理模块", "action": "读取", "output_objects": ["输入数据"], "downstream_feature_ids": ["F003"], "exception_path_ids": ["E001"]},
        },
        {
            "feature_id": "F003", "name": "输出结果", "statement": "输出结果", "classification": "distinguishing",
            "prior_art_status": {"verdict": "not_found_in_searched_outlets"}, "technical_effect": "形成可追溯结果",
            "evidence": [{"source": "交底书", "locator": "3"}],
            "claim_sites": [
                {"claim_number": 1, "part": "characterizing", "claim_type": "method", "execution_role": "result", "verbatim": "输出结果"},
                {"claim_number": 9, "part": "characterizing", "claim_type": "system", "execution_role": "storage", "actor": "结果存储模块", "verbatim": "结果存储模块"},
            ],
            "spec_sites": [{"section": "发明内容", "anchor": "输出结果"}], "drawing_sites": [],
            "flow": {"action_phase": "runtime_output", "input_objects": ["输入数据"], "processing_actor": "结果存储模块", "action": "输出并存储", "output_objects": ["结果"], "downstream_feature_ids": [], "exception_path_ids": []},
        },
    ]
    write_json(ledger, {
        "schema_id": "cn-patent-feature-ledger/v2", "case_id": "case", "generated_at": "2026-09-01", "legal_effect": "ADVISORY_ONLY",
        "closest_prior_art": [], "search_status": {"cnipa_manual_search": "completed", "statement": "已完成"}, "features": features,
        "claim_data_flows": [
            {"claim_number": 1, "claim_type": "method", "entry_feature_ids": ["F001"], "ordered_feature_ids": ["F001", "F002", "F003"], "merge_feature_ids": [], "normal_exit_feature_ids": ["F003"], "exception_path_ids": ["E001"], "storage_feature_ids": ["F003"]},
            {"claim_number": 9, "claim_type": "system", "entry_feature_ids": ["F001"], "ordered_feature_ids": ["F001", "F002", "F003"], "merge_feature_ids": [], "normal_exit_feature_ids": ["F003"], "exception_path_ids": ["E001"], "storage_feature_ids": ["F003"]},
        ],
        "method_system_pairs": [{"method_claim_number": 1, "system_claim_number": 9, "required_feature_ids": ["F001", "F002", "F003"]}],
        "exception_paths": [{"path_id": "E001", "trigger": "输入数据不完整", "action_feature_ids": ["F003"], "produces_value": True, "confidence": "low", "terminal_state": "低置信度完成", "reason_code": "INPUT_INCOMPLETE", "stored_fields": ["结果值", "置信度", "状态", "原因码"], "claim_sites": [{"claim_number": 1, "anchor": "低置信度完成状态及原因码"}, {"claim_number": 9, "anchor": "低置信度完成状态及原因码"}], "spec_sites": [{"section": "具体实施方式", "anchor": "低置信度完成状态及原因码"}], "drawing_relation_ids": []}],
    })
    return ledger, claims, specification, output


def run(ledger: Path, claims: Path, specification: Path, output: Path):
    return subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(ledger), "--claims", str(claims), "--specification", str(specification), "--output", str(output)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)


def test_v2_data_flow_and_exception_closure_pass(tmp_path):
    ledger, claims, specification, output = fixture(tmp_path)
    result = run(ledger, claims, specification, output)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_id"] == "cn-patent-feature-ledger-report/v2"
    assert report["counts"]["deterministic_fail"] == 0
    assert report["input_artifacts"]


def test_v2_missing_system_feature_is_blocked(tmp_path):
    ledger, claims, specification, output = fixture(tmp_path)
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["features"][1]["claim_sites"] = [payload["features"][1]["claim_sites"][0]]
    write_json(ledger, payload)
    result = run(ledger, claims, specification, output)
    assert result.returncode == 2
    codes = {item["rule_id"] for item in json.loads(output.read_text(encoding="utf-8"))["findings"]}
    assert "CN-LEDGER-PAIR-005" in codes


def test_v2_value_producing_exception_requires_confidence(tmp_path):
    ledger, claims, specification, output = fixture(tmp_path)
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["exception_paths"][0]["confidence"] = "unknown"
    write_json(ledger, payload)
    result = run(ledger, claims, specification, output)
    assert result.returncode == 2
    codes = {item["rule_id"] for item in json.loads(output.read_text(encoding="utf-8"))["findings"]}
    assert "CN-LEDGER-EXCEPTION-004" in codes
