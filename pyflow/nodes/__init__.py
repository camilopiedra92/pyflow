from __future__ import annotations

from pyflow.core.node import NodeRegistry
from pyflow.nodes.condition import ConditionNode
from pyflow.nodes.http import HttpNode
from pyflow.nodes.transform import TransformNode

default_registry = NodeRegistry()
default_registry.register(HttpNode)
default_registry.register(TransformNode)
default_registry.register(ConditionNode)
