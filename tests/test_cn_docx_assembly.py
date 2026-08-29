"""中国发明专利申请 DOCX 组装合同回归测试。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "patent-application-creator-CN"
    / "scripts"
    / "assemble_application_docx.py"
)
REFERENCE = (
    ROOT
    / "skills"
    / "patent-application-creator-CN"
    / "references"
    / "docx-assembly.md"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("cn_docx_assembler", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ASSEMBLER = _load_module()


def test_docx_assembly_skill_assets_are_utf8_and_documented():
    for path in (SCRIPT, REFERENCE):
        raw = path.read_bytes()
        assert raw
        assert not raw.startswith(b"\xef\xbb\xbf")
        raw.decode("utf-8")

    skill = (
        ROOT / "skills" / "patent-application-creator-CN" / "SKILL.md"
    ).read_text(encoding="utf-8")
    for required in (
        "assemble_application_docx.py",
        "references/docx-assembly.md",
        "m:oMath",
        "Strong",
        "visual_review_completed",
    ):
        assert required in skill
    assert "视觉检查默认关闭" in skill
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "只有用户明确要求视觉检查时才导出 PDF/PNG" in agents
    assert "不提供业务型 Slash Command" in readme
    assert "python-docx" in readme


def test_formula_parser_supports_explicit_and_legacy_blocks(tmp_path):
    module = ASSEMBLER
    spec = tmp_path / "说明书.md"
    spec.write_text(
        """# 示例装置

## 技术领域

患者年龄为 $a$，转换系数为 $C(P,a)$。

## 背景技术

$$
C(P,a)=C(P,a_i)+(a-a_i)×[C(P,a_(i+1))-C(P,a_i)]/(a_(i+1)-a_i)
$$

## 发明内容

```math
ED_CT=Q_CT×C_CT(P,a)
```

## 附图说明

图1是示意图。

## 具体实施方式

m_k=m_(k-1)+(x_k-m_(k-1))/k。
""",
        encoding="utf-8",
    )

    items = module.parse_specification(spec)
    assert [item.kind for item in items].count("formula") == 3
    assert [item.text for item in items if item.kind == "heading"] == [
        "技术领域",
        "背景技术",
        "发明内容",
        "附图说明",
        "具体实施方式",
    ]
    symbols = module.collect_math_symbols(items)
    tokens = module.tokenize_inline_math("患者年龄为 $a$，转换系数为 $C(P,a)$。", symbols)
    assert [value for is_math, value in tokens if is_math] == ["a", "C(P,a)"]


def test_claim_abstract_and_figure_contracts(tmp_path):
    module = ASSEMBLER
    claims = tmp_path / "权利要求书.md"
    claims.write_text("# 权利要求书\n\n1. 第一项。\n\n2. 第二项。\n", encoding="utf-8")
    assert module.parse_claims(claims) == ["第一项。", "第二项。"]

    abstract = tmp_path / "说明书摘要.md"
    abstract.write_text("# 示例装置\n\n这是摘要。\n\n摘要附图：图2。\n", encoding="utf-8")
    assert module.parse_abstract(abstract) == ("这是摘要。", 2)

    drawing_dir = tmp_path / "说明书附图"
    drawing_dir.mkdir()
    for number in (1, 2):
        (drawing_dir / f"图{number}.png").write_bytes(b"png-placeholder")
    index = tmp_path / "说明书附图.md"
    index.write_text(
        """# 说明书附图

## 图1 系统结构示意图

![图1](说明书附图/图1.png)

## 图2 方法流程图

![图2](说明书附图/图2.png)
""",
        encoding="utf-8",
    )
    figures = module.parse_figures(index)
    assert [(figure.number, figure.title) for figure in figures] == [
        (1, "系统结构示意图"),
        (2, "方法流程图"),
    ]


def test_word_formula_conversion_is_fail_closed_off_windows(monkeypatch, tmp_path):
    module = ASSEMBLER
    monkeypatch.setattr(module.sys, "platform", "linux")
    registry = module.MathRegistry()
    registry.add("ED_CT=Q_CT×C_CT(P,a)")
    try:
        module.process_with_word(tmp_path / "missing.docx", registry, None)
    except RuntimeError as exc:
        assert "Microsoft Word" in str(exc)
    else:  # pragma: no cover - 防止错误放行
        raise AssertionError("非 Windows 环境不应静默跳过 Word 原生公式转换")


def test_visual_review_is_opt_in(monkeypatch, tmp_path):
    module = ASSEMBLER
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["assemble_application_docx.py", "--case-dir", str(tmp_path)],
    )
    args = module.parse_args()
    assert args.visual_review is False

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "assemble_application_docx.py",
            "--case-dir",
            str(tmp_path),
            "--visual-review",
        ],
    )
    args = module.parse_args()
    assert args.visual_review is True
