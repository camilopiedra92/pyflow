from __future__ import annotations

from pyflow.core.node import NodeRegistry
from pyflow.nodes.alert import AlertNode
from pyflow.nodes.condition import ConditionNode
from pyflow.nodes.http import HttpNode
from pyflow.nodes.storage import StorageNode
from pyflow.nodes.transform import TransformNode

default_registry = NodeRegistry()
default_registry.register(HttpNode)
default_registry.register(TransformNode)
default_registry.register(ConditionNode)
default_registry.register(AlertNode)
default_registry.register(StorageNode)
