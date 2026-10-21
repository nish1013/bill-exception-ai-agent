from typing import Any

import graphene
from graphql import BooleanValueNode, FloatValueNode, IntValueNode, StringValueNode, ValueNode
from graphql.pyutils import Undefined


class MinorUnits(graphene.Scalar):
    """An integer amount in minor units. Any other value returns VALIDATION (D14)."""

    @staticmethod
    def serialize(value: int) -> int:
        return value

    @staticmethod
    def parse_value(value: Any) -> Any:
        # Money refuses a float in the resolver, so the error carries status 400 (D48).
        return value

    @staticmethod
    def parse_literal(node: ValueNode, _variables: Any = None) -> Any:
        if isinstance(node, IntValueNode):
            return int(node.value)
        if isinstance(node, FloatValueNode):
            return float(node.value)
        if isinstance(node, StringValueNode | BooleanValueNode):
            return node.value
        return Undefined
