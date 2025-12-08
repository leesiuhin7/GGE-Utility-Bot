import pytest
from typing_extensions import Any, Type, TypedDict

from gge_utility_bot import utils


@pytest.mark.parametrize("seconds, expected", [
    (0, "0s"),
    (46, "46s"),
    (120, "2m 0s"),
    (283, "4m 43s"),
    (3600, "1h 0m 0s"),
    (86400, "24h 0m 0s"),
])
def test_as_compound_time(seconds: int, expected: str) -> None:
    assert utils.as_compound_time(seconds) == expected


class Inner(TypedDict):
    x: int
    y: float


class NestedDict(TypedDict):
    a: str
    b: list[int]
    nested: Inner


@pytest.mark.parametrize("obj, obj_type, expected", [
    (1, int, True),
    (["a", "b", "cd"], list[str], True),
    ("", str, True),
    (
        {
            "a": "hello",
            "b": [0, 1, 2],
            "nested": {
                "x": 10,
                "y": 0.1,
            }
        },
        NestedDict,
        True,
    ),
    ("not int", int, False),
    ([1, "2", 3], list[int], False),
    (("x", "y", "z"), list[str], False),
    (
        {
            "a": "hello",
            "b": [0, 1, "2"],
            "nested": {
                "x": 10,
                "y": 0.1,
            }
        },
        NestedDict,
        False,
    ),
    (
        {
            "a": "hello",
            "b": [0, 1, 2],
            "nested": {
                "x": 10,
                "y": 0.1,
            },
            "extra": "not allowed",
        },
        NestedDict,
        False,
    ),
])
def test_validate_type(
    obj: Any,
    obj_type: Type,
    expected: bool,
) -> None:
    assert utils.validate_type(obj, obj_type) == expected
