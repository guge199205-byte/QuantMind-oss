"""Tests for the AST whitelist checker."""

import pytest

from backend.services.engine.strategy_lab.runner.ast_checker import (
    ASTCheckError,
    ALLOWED_MODULES,
    assert_safe,
    check_source,
    discover_hooks,
)

CLEAN_SCRIPT = """
import numpy as np
import pandas as pd
import math

def setup(ctx):
    ctx.universe = 'csi300'
    ctx.start = '2020-01-01'
    ctx.end = '2025-12-31'
    ctx.cash = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(bar.symbol, n=22, field='close')
    if len(closes) < 22:
        return
    s1 = closes.max() * 0.786
    if abs(bar.close - s1) / s1 < 0.03:
        ctx.buy(bar.symbol, weight=0.05, reason='S1_hit')
"""


def test_clean_script_passes():
    issues = check_source(CLEAN_SCRIPT)
    assert issues == []
    assert_safe(CLEAN_SCRIPT)


def test_discover_hooks():
    hooks = discover_hooks(CLEAN_SCRIPT)
    assert hooks == {"setup", "on_bar"}


def test_missing_setup_rejected():
    src = """
def on_bar(ctx, bar): pass
"""
    issues = check_source(src)
    codes = {i.code for i in issues}
    assert "E_HOOK_MISSING" in codes


def test_skip_hook_check():
    src = "x = 1\n"
    issues = check_source(src, require_hooks=False)
    assert issues == []


@pytest.mark.parametrize(
    "snippet,expected_code",
    [
        ("import os\ndef setup(ctx): pass", "E_IMPORT"),
        ("import sys\ndef setup(ctx): pass", "E_IMPORT"),
        ("import subprocess\ndef setup(ctx): pass", "E_IMPORT"),
        ("import socket\ndef setup(ctx): pass", "E_IMPORT"),
        ("import ctypes\ndef setup(ctx): pass", "E_IMPORT"),
        ("from os import path\ndef setup(ctx): pass", "E_IMPORT"),
        ("from . import x\ndef setup(ctx): pass", "E_RELIMPORT"),
    ],
)
def test_forbidden_imports(snippet, expected_code):
    issues = check_source(snippet)
    assert any(i.code == expected_code for i in issues), [i.code for i in issues]


@pytest.mark.parametrize(
    "snippet,banned",
    [
        ("def setup(ctx):\n    exec('print(1)')", "exec"),
        ("def setup(ctx):\n    eval('1+1')", "eval"),
        ("def setup(ctx):\n    open('/tmp/x', 'w')", "open"),
        ("def setup(ctx):\n    __import__('os')", "__import__"),
        ("def setup(ctx):\n    compile('x=1', '<x>', 'exec')", "compile"),
    ],
)
def test_forbidden_calls(snippet, banned):
    issues = check_source(snippet)
    assert any(i.code == "E_CALL" and banned in i.message for i in issues)


def test_forbidden_dunder():
    src = """
def setup(ctx):
    cls = ().__class__.__bases__
"""
    issues = check_source(src)
    codes = [i.code for i in issues]
    assert codes.count("E_DUNDER") >= 1


def test_async_hook_rejected():
    src = """
async def setup(ctx):
    pass
"""
    issues = check_source(src)
    assert any(i.code == "E_ASYNC" for i in issues)


def test_syntax_error_returns_e_syntax():
    issues = check_source("def setup(ctx :::")
    assert len(issues) == 1
    assert issues[0].code == "E_SYNTAX"


def test_assert_safe_raises_with_issues():
    with pytest.raises(ASTCheckError) as exc:
        assert_safe("import os\ndef setup(ctx): pass")
    assert any(i.code == "E_IMPORT" for i in exc.value.issues)


def test_allowed_modules_seed_includes_core_libs():
    for m in ("numpy", "pandas", "math", "talib"):
        assert m in ALLOWED_MODULES


def test_qlib_data_subpath_allowed():
    src = """
from qlib.data import D
def setup(ctx):
    pass
"""
    issues = check_source(src)
    assert all(i.code != "E_IMPORT" for i in issues)


def test_smuggle_via_with_still_caught():
    src = """
def setup(ctx):
    with open('/tmp/x', 'w') as f:
        f.write('hi')
"""
    issues = check_source(src)
    assert any(i.code == "E_CALL" for i in issues)


def test_multiple_issues_reported_together():
    src = """
import os
import sys

def setup(ctx):
    eval('1')
    exec('1')
"""
    issues = check_source(src)
    assert sum(1 for i in issues if i.code == "E_IMPORT") == 2
    assert sum(1 for i in issues if i.code == "E_CALL") == 2
