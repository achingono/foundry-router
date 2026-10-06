"""Deterministic string skipping preserves finite strict JSON parsing."""

import json
import random

import pytest

from foundry_router.api.adapters.google_schema import load_bounded_json


@pytest.mark.parametrize(
    "value", ["[]{}", '"[]\\{}', '\\"' * 50, "😀{}\n\t", "\\" * 1000, "x" * 10000]
)
def test_braces_quotes_and_backslash_parity_inside_strings(value):
    wire = json.dumps({"value": value})
    assert load_bounded_json(wire) == {"value": value}


def test_depth_bound_before_decoder_and_inside_strings():
    wire = "[" * 32 + json.dumps("[" * 1000 + '"\\' * 1000) + "]" * 32
    assert load_bounded_json(wire)
    with pytest.raises(ValueError, match="depth"):
        load_bounded_json("[" + wire + "]")


@pytest.mark.parametrize(
    "wire", ['"unclosed', '"\\', '"escaped\\"', '"bad\ncontrol"', '{"x":1,"x":2}', "[NaN]", '"\\q"']
)
def test_malformed_strings_and_strict_values_still_reject(wire):
    with pytest.raises(ValueError):
        load_bounded_json(wire)


def test_seeded_structural_strings_match_json_decoder():
    source = random.Random(271828)
    alphabet = '{}[]"\\😀 abc\n'
    for _ in range(2000):
        value = "".join(source.choice(alphabet) for _ in range(source.randrange(100)))
        wire = json.dumps([value, {value: value}], ensure_ascii=False)
        assert load_bounded_json(wire) == json.loads(wire)


@pytest.mark.parametrize("value", ["x" * 2000000, "\\" * 1000000, '"' * 600000])
def test_maximum_string_workload_is_bounded_and_lossless(value):
    wire = json.dumps(value)
    assert load_bounded_json(wire, max_bytes=2097152) == value


@pytest.mark.parametrize("slash_count", [255, 256, 257, 511, 512, 513, 999999])
def test_escaped_run_boundaries_and_long_backslash_suffix_remain_lossless(slash_count):
    value = '"' + "\\" * slash_count + '"[{}]'
    wire = json.dumps(value)
    assert load_bounded_json(wire, max_bytes=2097152) == value


@pytest.mark.parametrize("tail", ["\\", '\\"', "\\q", '"\\', "\n"])
def test_dense_escaped_run_cannot_hide_malformed_tail(tail):
    wire = '"' + '\\"' * 1024 + tail
    with pytest.raises(ValueError):
        load_bounded_json(wire)


def test_depth_after_dense_escaped_run_is_still_checked_before_decoder():
    value = '"' * 10000 + "\\" * 513 + "[]{}"
    wire = "[" * 32 + json.dumps(value) + "]" * 32
    assert load_bounded_json(wire) == json.loads(wire)
    with pytest.raises(ValueError, match="depth"):
        load_bounded_json("[" + wire + "]")
