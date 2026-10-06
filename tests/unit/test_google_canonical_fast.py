"""Exact built-in fast path is equivalent; subclass output retains strict parsing."""

import json
import random

import pytest

from foundry_router.api.adapters.google_schema import load_bounded_json
from foundry_router.api.google_state import canonical_bytes, canonical_wire_bytes


class DuplicateDict(dict):
    def items(self):
        return [("x", 1), ("x", 2)]

    def values(self):
        return [1, 2]


class PlainDict(dict):
    pass


class PlainString(str):
    pass


def oracle(value, max_bytes=2097152):
    wire = canonical_wire_bytes(value, max_bytes=max_bytes)
    load_bounded_json(wire.decode(), max_bytes=max_bytes)
    return wire


def test_duplicate_emitting_subclass_is_still_rejected():
    value = DuplicateDict(x=1)
    assert canonical_wire_bytes(value) == b'{"x":1,"x":2}'
    with pytest.raises(ValueError):
        canonical_bytes(value)


@pytest.mark.parametrize("value", [PlainDict(x=1), [PlainString("x")], {PlainString("x"): 2}])
def test_harmless_subclasses_retain_original_acceptance(value):
    assert canonical_bytes(value) == oracle(value)


def test_subclass_does_not_skip_bounds_on_later_child():
    value = [PlainString("x"), [0] * 16383]
    with pytest.raises(ValueError):
        canonical_bytes(value)


@pytest.mark.parametrize("depth", [31, 32, 33])
def test_depth_boundary_matches_original(depth):
    value = "x"
    for _ in range(depth):
        value = [value]
    if depth > 32:
        with pytest.raises(ValueError):
            canonical_bytes(value)
    else:
        assert canonical_bytes(value) == oracle(value)


@pytest.mark.parametrize("depth", [31, 32, 33, 34])
@pytest.mark.parametrize("shape", ["list", "dict", "tuple", "mixed"])
def test_empty_container_structural_depth_matches_original(depth, shape):
    value = []
    for index in range(depth - 1):
        kind = ("list", "dict", "tuple")[index % 3] if shape == "mixed" else shape
        if kind == "list":
            value = [value]
        elif kind == "dict":
            value = {"x": value}
        else:
            value = (value,)
    # The wire-only helper retains its original zero-based value-depth contract.
    if depth <= 33:
        assert json.loads(canonical_wire_bytes(value)) is not None
    else:
        with pytest.raises(ValueError):
            canonical_wire_bytes(value)
    if depth <= 32:
        assert canonical_bytes(value) == oracle(value)
    else:
        with pytest.raises(ValueError):
            canonical_bytes(value)
        with pytest.raises(ValueError):
            oracle(value)


@pytest.mark.parametrize("size", [16382, 16383, 16384])
def test_node_boundary_matches_original(size):
    value = [None] * size
    if size > 16383:
        with pytest.raises(ValueError):
            canonical_bytes(value)
    else:
        assert canonical_bytes(value) == oracle(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "\ud800", {1: "x"}, b"x"])
def test_invalid_values_retain_rejection(value):
    with pytest.raises(ValueError):
        canonical_bytes(value)


def test_exact_wire_cap_and_tuple_array_mapping():
    value = ("é", -0.0, True, None)
    expected = oracle(value)
    assert canonical_bytes(value, max_bytes=len(expected)) == expected
    with pytest.raises(ValueError):
        canonical_bytes(value, max_bytes=len(expected) - 1)


def test_seeded_exact_builtin_trees_match_old_oracle():
    source = random.Random(481516)

    def value(depth=0):
        atom = source.choice([None, True, False, 123, -5, 0.0, -0.0, '😀\\"{}[]'])
        if depth > 4 or source.randrange(3) == 0:
            return atom
        children = [value(depth + 1) for _ in range(source.randrange(5))]
        return source.choice(
            [children, tuple(children), {str(i): item for i, item in enumerate(children)}]
        )

    for _ in range(2000):
        sample = value()
        assert canonical_bytes(sample) == oracle(sample)
        assert json.loads(canonical_bytes(sample)) == json.loads(oracle(sample))
