"""CLI 冒烟与失败路径。退出码约定：0 审查完成；2 用法/输入错误。"""
import io
import json

import pytest

from food_label_checker.cli import main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "flcheck" in capsys.readouterr().out


def test_no_command_prints_help_exit_2(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_check_sample_dual_ruleset(sample_text, tmp_path, capsys):
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    assert main(["check", str(target), "--ruleset", "both"]) == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert set(data["results"]) == {"gb7718-2011", "gb7718-2025"}
    # 样例缺净含量/营养成分表（两版都报）+ 缺到期日/盐油糖提示语（仅 2025 报）
    assert data["dual_diff"]["new_fails"] == ["MAND-EXPIRY-01", "SALT-NOTICE-01"]
    assert data["card"]["fields"]["food_name"]


def test_check_single_ruleset(sample_text, tmp_path, capsys):
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    assert main(["check", str(target), "--ruleset", "2011"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data["results"]) == {"gb7718-2011"}
    assert "dual_diff" not in data


def test_parse_subcommand(sample_text, tmp_path, capsys):
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    assert main(["parse", str(target)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["fields"]["food_name"]["key"] == "food_name"


def test_check_missing_file_exit_2(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope.txt")]) == 2
    assert "不存在" in capsys.readouterr().err


def test_check_bad_encoding_exit_2(tmp_path, capsys):
    target = tmp_path / "bad.txt"
    target.write_bytes(b"\xff\xfe\x00\x01not-utf8")
    assert main(["check", str(target)]) == 2
    assert "UTF-8" in capsys.readouterr().err


def test_unknown_ruleset_exit_2(sample_text, tmp_path, capsys):
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    assert main(["check", str(target), "--ruleset", "1990"]) == 2
    assert "未知规则集" in capsys.readouterr().err


def test_bench_requires_subcommand_exit_2(capsys):
    """M4：bench 已实现，裸命令提示需要子命令（parse/e2e）。"""
    assert main(["bench"]) == 2
    assert "需要子命令" in capsys.readouterr().err


def test_web_subcommand_help_wired():
    """M5：web 子命令已实现（--help 走 argparse 正常退出，不真正起服务）。"""
    import contextlib

    with contextlib.redirect_stdout(io.StringIO()) as buf, pytest.raises(SystemExit) as ei:
        main(["web", "--help"])
    assert ei.value.code == 0
    assert "--host" in buf.getvalue()


def test_check_format_table(sample_text, tmp_path, capsys):
    """M5：check --format table 人读摘要（含统计行与结论行，非 JSON）。"""
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    assert main(["check", str(target), "--format", "table"]) == 0
    out = capsys.readouterr().out
    assert "[flcheck] 食品标签合规审查" in out
    assert "■ gb7718-2011" in out and "■ gb7718-2025" in out
    assert "✗ 不合规" in out
    assert "双标尺对照" in out and "MAND-EXPIRY-01" in out


def test_check_report_generates_docx(sample_text, tmp_path, capsys):
    """M5：check --report 生成 docx（需 report 扩展），stdout 保持纯 JSON。"""
    pytest.importorskip("docx")
    target = tmp_path / "label.txt"
    target.write_text(sample_text, encoding="utf-8")
    report_path = tmp_path / "out" / "report.docx"
    assert main(["check", str(target), "--report", str(report_path)]) == 0
    assert report_path.exists()
    captured = capsys.readouterr()
    assert "docx 报告已生成" in captured.err
    data = json.loads(captured.out)  # stdout 仍是完整 JSON
    assert data["results"]


def test_check_report_missing_file_still_exit_2(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope.txt"), "--report", "x.docx"]) == 2
    assert "不存在" in capsys.readouterr().err
