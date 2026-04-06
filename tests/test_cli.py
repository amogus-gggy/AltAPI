"""Tests for altapi.cli (Click)."""

from pathlib import Path

from click.testing import CliRunner

from altapi.cli import cli, _get_available_templates


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "2.0.0" in result.output


def test_list_templates():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-templates"])
    assert result.exit_code == 0
    assert "basic" in result.output or "full" in result.output


def test_get_available_templates():
    names = _get_available_templates()
    assert isinstance(names, list)
    assert "basic" in names


def test_create_project_basic(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["create", "mytestapi", "--template", "basic"])
        assert result.exit_code == 0
        assert Path("mytestapi").is_dir()
        assert Path("mytestapi/app.py").is_file()


def test_show_template_basic():
    runner = CliRunner()
    result = runner.invoke(cli, ["show-template", "basic"])
    assert result.exit_code == 0
    assert "basic" in result.output.lower() or "Template" in result.output


def test_copy_template_missing_exits(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["create", "x", "--template", "does_not_exist_ever"])
        assert result.exit_code != 0
