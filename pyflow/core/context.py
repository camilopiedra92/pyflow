from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionContext:
    workflow_name: str
    run_id: str
    _results: dict[str, object] = field(default_factory=dict, repr=False)
    _errors: dict[str, str] = field(default_factory=dict, repr=False)

    def set_result(self, node_id: str, result: object) -> None:
        self._results[node_id] = result

    def get_result(self, node_id: str) -> object:
        return self._results[node_id]

    def has_result(self, node_id: str) -> bool:
        return node_id in self._results

    def all_results(self) -> dict[str, object]:
        return dict(self._results)

    def set_error(self, node_id: str, error: str) -> None:
        self._errors[node_id] = error

    def get_error(self, node_id: str) -> str:
        return self._errors[node_id]

    def has_error(self, node_id: str) -> bool:
        return node_id in self._errors
