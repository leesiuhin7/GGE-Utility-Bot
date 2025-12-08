import asyncio
import io
import json

import pydantic
from typing_extensions import (
    Any,
    Awaitable,
    Callable,
    Generic,
    ParamSpec,
    Type,
)

P = ParamSpec("P")


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


def kid_to_name(kid: int) -> str | None:
    name_map = {
        0: "The Great Empire",
        1: "The Burning Sands",
        2: "The Everwinter Glacier",
        3: "The Fire Peaks",
        4: "The Storm Islands",
    }
    return name_map.get(kid)


class _TypeValidator:
    CACHE_MAX_LEN: int = 1024
    _cache_keys: list[Type] = []
    _cache_items: list[pydantic.TypeAdapter] = []

    @classmethod
    def validate_type(cls, obj: Any, obj_type: Type) -> bool:
        try:
            # Use cache
            type_adapter = cls._cache_items[
                cls._cache_keys.index(obj_type)
            ]
        except:
            type_adapter = pydantic.TypeAdapter(obj_type)
            # Add to cache
            cls._cache_keys.insert(0, obj_type)
            cls._cache_items.insert(0, type_adapter)

            # Remove excess
            if len(cls._cache_keys) > cls.CACHE_MAX_LEN:
                cls._cache_keys.pop()
                cls._cache_items.pop()

        try:
            type_adapter.validate_python(
                obj, strict=True, extra="forbid",
            )
            return True
        except pydantic.ValidationError:
            return False


def validate_type(obj: Any, obj_type: Type) -> bool:
    """
    Checks whether an object is the specified type.

    :param obj: The object
    :type obj: Any
    :param obj_type: The type to compare the object against
    :type obj_type: Type
    :return: True if the object's type matches, False otherwise
    :rtype: bool
    """
    return _TypeValidator.validate_type(obj, obj_type)


class AsyncCallbackManager(Generic[P]):
    def __init__(self) -> None:
        self._id = 0
        self._callbacks: dict[
            int,  Callable[P, Awaitable[None]],
        ] = {}

    async def on_event(
        self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        await asyncio.gather(
            *[
                callback(*args, **kwargs)
                for callback in self._callbacks.values()
            ],
            return_exceptions=True,
        )

    def add_callback(
        self,
        callback: Callable[P, Awaitable[None]],
    ) -> int:
        callback_id = self._new_id()
        self._callbacks[callback_id] = callback
        return callback_id

    def remove_callback(self, callback_id: int) -> None:
        if callback_id in self._callbacks:
            del self._callbacks[callback_id]

    def _new_id(self) -> int:
        new_id = self._id
        self._id += 1
        return new_id
