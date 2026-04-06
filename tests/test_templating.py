"""Tests for altapi.templating."""

import pytest

from altapi.templating import (
    Jinja2Templates,
    TemplateResponse,
    get_default_templates_directory,
    render_template,
    set_default_templates_directory,
)


def test_set_get_default_templates_directory(tmp_path):
    d = tmp_path / "tmpl"
    d.mkdir()
    set_default_templates_directory(d)
    assert get_default_templates_directory() == str(d)


def test_jinja2_templates_render(tmp_path):
    (tmp_path / "hello.html").write_text("<p>{{ name }}</p>", encoding="utf-8")
    t = Jinja2Templates(str(tmp_path))
    html = t.render("hello.html", {"name": "World"})
    assert "<p>World</p>" in html


def test_template_response(tmp_path):
    (tmp_path / "page.html").write_text("<html>{{ x }}</html>", encoding="utf-8")
    t = Jinja2Templates(str(tmp_path))
    r = t.TemplateResponse("page.html", {"x": 1})
    assert r.status_code == 200
    assert b"1" in r._encoded_body


def test_render_template_function(tmp_path):
    (tmp_path / "x.html").write_text("{{ a }}", encoding="utf-8")
    set_default_templates_directory(tmp_path)
    r = render_template("x.html", {"a": "ok"})
    assert r.status_code == 200
    assert b"ok" in r._encoded_body
