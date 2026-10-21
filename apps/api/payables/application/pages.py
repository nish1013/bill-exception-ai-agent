from dataclasses import dataclass


@dataclass(frozen=True)
class ListPage[T]:
    items: list[T]
    total_count: int
