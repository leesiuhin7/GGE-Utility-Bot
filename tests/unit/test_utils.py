import pytest
import copy
from typing_extensions import Sequence, Any, Type, TypedDict

import utils


@pytest.mark.parametrize("config_input, expected", [
    (
        '{"path": ["xyz", "xyz"], "action": "delete", "value": "ignore"}',
        utils.ParsedConfigInput(
            path=["xyz", "xyz"],
            action="delete",
            value=None,
        ),
    ),
    (
        '{"path": ["abc", "efg"], "action": "set", "value": "xyz"}',
        utils.ParsedConfigInput(
            path=["abc", "efg"],
            action="set",
            value="xyz",
        ),
    ),
])
def test_parse_config_input_valid(
    config_input: str,
    expected: str,
) -> None:
    assert utils.parse_config_input(config_input) == expected


@pytest.mark.parametrize("config_input", [
    "not json",
    "[]",
    '{"path": ["valid path"]}',
    '{"path": ["bad", 123, 456], "action": "delete"}',
    '{"path": ["xyz"], "action": "set"}',
    '{"path": ["abc"], "action": "sett", "value": "some value"',
    '{"path": "not a path", "action": "delete"}',
])
def test_parse_config_input_invalid(
    config_input: str,
) -> None:
    assert utils.parse_config_input(config_input) is None


PATH_DICT_DATA = {
    "name": "Bob",
    "list-like": {
        "0": {
            "age": 40,
            "birthday": "Jan 10",
        },
        "1": {
            "weight": 60,
            "height": 180,
        },
    },
    "list": [1, 2, 3],
}


@pytest.fixture
def path_dict() -> utils.PathDict:
    path_dict = utils.PathDict()
    path_dict._dict_obj = copy.deepcopy(PATH_DICT_DATA)
    return path_dict


@pytest.fixture
def clean_path_dict() -> utils.PathDict:
    return utils.PathDict()


@pytest.mark.parametrize("path, expected", [
    ([], PATH_DICT_DATA),
    (["name"], PATH_DICT_DATA["name"]),
    (["list-like", "1"], PATH_DICT_DATA["list-like"]["1"]),
])
def test_path_dict_get_valid(
    path_dict: utils.PathDict,
    path: Sequence[str],
    expected: Any,
) -> None:
    assert path_dict.get(path) == expected


@pytest.mark.parametrize("path, expected_error", [
    (["non-existant"], KeyError),
    (["list-like", "2"], KeyError),
    (["list", "0"], TypeError),
])
def test_path_dict_get_invalid(
    path_dict: utils.PathDict,
    path: Sequence[str],
    expected_error: Type[KeyError | TypeError],
) -> None:
    with pytest.raises(expected_error):
        path_dict.get(path)


@pytest.mark.parametrize("paths, values, expected", [
    ((["key"],), (10,), {"key": 10}),
    ((["key1", "key2"],), (12,), {"key1": {"key2": 12}}),
    (
        (["nested"],),
        ({"key1": 5, "key2": 6},),
        {"nested": {"key1": 5, "key2": 6}},
    ),
    (
        (["access1"], ["access2"]),
        ("value1", "value2"),
        {"access1": "value1", "access2": "value2"},
    ),
    (
        (["overwritten"], ["overwritten"]),
        ("value1", "value2"),
        {"overwritten": "value2"},
    ),
])
def test_path_dict_update_set_valid(
    clean_path_dict: utils.PathDict,
    paths: tuple[Sequence[str]],
    values: tuple[Any],
    expected: dict[Any, Any],
) -> None:
    for path, value in zip(paths, values):
        assert clean_path_dict.update(path, "set", value) is True

    assert clean_path_dict._dict_obj == expected


@pytest.mark.parametrize("path, value", [
    (["list", "key"], None),
    ([], "not a dict"),
])
def test_path_dict_update_set_invalid(
    path_dict: utils.PathDict,
    path: Sequence[str],
    value: Any,
) -> None:
    assert path_dict.update(path, "set", value) is False


@pytest.mark.parametrize("path, expected_result, expected_value", [
    ([], True, {}),
    (["list-like"], True, {"name": "Bob", "list": [1, 2, 3]}),
    (
        ["list-like", "1"],
        True,
        {
            "name": "Bob",
            "list-like": {
                "0": {
                    "age": 40,
                    "birthday": "Jan 10",
                },
            },
            "list": [1, 2, 3],
        },
    ),
    (["surname"], False, PATH_DICT_DATA),
])
def test_path_dict_update_delete(
    path_dict: utils.PathDict,
    path: Sequence[str],
    expected_result: bool,
    expected_value: dict[Any, Any],
) -> None:
    assert path_dict.update(path, "delete") == expected_result
    assert path_dict._dict_obj == expected_value


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
