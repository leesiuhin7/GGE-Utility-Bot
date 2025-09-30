import json
import io
from typing import TypedDict, Literal, Any, overload, Sequence


class ParsedConfigInput(TypedDict):
    path: list[str]
    action: Literal["set", "delete"]
    value: Any | None


def parse_config_input(
    config_input: str,
) -> ParsedConfigInput | None:
    try:
        json_msg = json.loads(config_input)
        path = json_msg["path"]
        action = json_msg["action"]
        value = json_msg.get("value", None)
    except:
        return

    # Type checking for path
    if not isinstance(path, list):
        return
    if not all([isinstance(key, str) for key in path]):
        return

    if action == "set":
        if "value" not in json_msg:
            return

        parsed: ParsedConfigInput = {
            "path": path,
            "action": action,
            "value": value,
        }
        return parsed
    elif action == "delete":
        parsed: ParsedConfigInput = {
            "path": path,
            "action": action,
            "value": None,
        }
        return parsed
    else:
        return


def serialize_as_display_buffer(
    obj: Any,
    sort_keys: bool,
) -> io.BytesIO:
    """
    Serializes an object into its json counterpart for display,
    uses a empty dictionary if the object is not serializable.

    :return: A BytesIO buffer of the serialized object
    :rtype: io.BytesIO
    """
    json_bytes = json.dumps(
        obj,
        indent=2,
        sort_keys=sort_keys,
        default=lambda _: {},
    ).encode("utf-8")
    buffer = io.BytesIO(json_bytes)
    return buffer


class PathDict:
    """
    A class for read / write operation on a dict-like object using
    a path represented as a list of keys.
    """

    def __init__(self) -> None:
        self._dict_obj: dict[Any, Any] = {}

    @overload
    def update(
        self,
        path: Sequence[str],
        action: Literal["set"],
        value: Any,
    ) -> bool: ...

    @overload
    def update(
        self,
        path: Sequence[str],
        action: Literal["delete"],
    ) -> bool: ...

    def update(
        self,
        path: Sequence[str],
        action: Literal["set", "delete"],
        value: Any = None,
    ) -> bool:
        """
        Updates the dictionary using a path.

        :param path: A list of keys where the first item is used first
        :type path: Sequence[str]
        :param action: "set" overwrites the branch specified by path,
            will create a vaild path if it doesn't exist.
            "delete" removes the branch and any sub-branches specified
            by path.
        :type action: Literal["set", "delete"]
        :param value: The value used for overwriting, must be a 
            dict if path is empty, defaults to None
        :type value: Any, optional
        :return: True if update was successful, False otherwise
        :rtype: bool
        """
        # Traverse path
        current_obj = self._dict_obj
        for key in path[:-1]:
            if not isinstance(current_obj, dict):
                return False
            # Creating branches along the way if needed
            current_obj = current_obj.setdefault(key, {})

        if len(path) > 0:
            key = path[-1]
            if action == "set":
                current_obj[key] = value
            elif action == "delete":
                if key in current_obj:
                    del current_obj[key]
                else:
                    return False
        else:  # Path is empty
            if action == "set":
                # Requires overwirte value as dict
                if not isinstance(value, dict):
                    return False
                # Mutates the value instead of setting it
                self._dict_obj.clear()
                self._dict_obj.update(value)
            elif action == "delete":
                # Simply empties the dict
                self._dict_obj.clear()

        return True

    def get(self, path: Sequence[str]) -> Any:
        """
        Gets the value with the given path in the dictionary.

        :param path: A list of keys where the first item is used first
        :type path: Sequence[str]
        :raises KeyError: If path is not valid
        :raises TypeError: If path is not valid 
        :return: The value with the given path
        :rtype: Any
        """
        # Raises KeyError
        current_obj = self._dict_obj
        for key in path:
            if not isinstance(current_obj, dict):
                raise TypeError
            current_obj = current_obj[key]  # Raises KeyError

        return current_obj


def as_compound_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds // 60) % 60
    s = seconds % 60

    if h != 0:
        return f"{h}h {m}m {s}s"
    elif m != 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"
