import pytest
from pathlib import Path
from pyflow.core.loader import load_workflow, load_all_workflows
from pyflow.core.models import WorkflowDef

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestLoadWorkflow:
    def test_load_from_file(self):
        wf = load_workflow(FIXTURES / "simple.yaml")
        assert isinstance(wf, WorkflowDef)
        assert wf.name == "simple-workflow"
        assert len(wf.nodes) == 1

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_workflow(Path("/nonexistent/workflow.yaml"))

    def test_load_invalid_yaml_raises(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("not: valid: yaml: [[[")
            bad_path = Path(f.name)
        with pytest.raises(Exception):
            load_workflow(bad_path)
        bad_path.unlink()


class TestLoadAllWorkflows:
    def test_load_directory(self):
        workflows = load_all_workflows(FIXTURES)
        assert len(workflows) >= 1
        assert all(isinstance(wf, WorkflowDef) for wf in workflows)
