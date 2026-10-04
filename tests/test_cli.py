"""CLI 冒烟与失败路径。退出码约定：0 审查完成；2 用法/输入错误。"""
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


def test_unimplemented_subcommand_exit_2(capsys):
    assert main(["bench"]) == 2
    assert "尚未实现" in capsys.readouterr().err
