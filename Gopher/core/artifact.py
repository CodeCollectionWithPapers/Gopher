import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class BuggyArtifact:

    project_name: str
    bug_id: str
    file_path: str
    method_name: str
    buggy_line_no: int
    source_code: str
    language: str = "java"

    @property
    def identifier(self) -> str:
        return f"{self.project_name}-{self.bug_id}"

@dataclass
class DualLayerContext:
    """
    Layer 1 && Layer 2
    """
    data_dependency_slice: str = ""
    control_dependency_slice: str = ""
    peripheral_context: str = ""

    def is_empty(self) -> bool:
        return not (self.data_dependency_slice or self.peripheral_context)

@dataclass
class RepairSession:

    artifact: BuggyArtifact
    context: DualLayerContext
    workspace_dir: str
    feedback_history: List[str] = field(default_factory=list)

    def get_context_for_round(self, round_num: int) -> Dict[str, str]:

        if round_num == 1:
            return {"module_3_context": "none"}

        elif round_num == 2:
            return {
                "module_3_context": "slice",
                "data_dependency_slice": self.context.data_dependency_slice,
                "control_dependency_slice": self.context.control_dependency_slice
            }

        elif round_num == 3:
            return {
                "module_3_context": "periphery",
                "class_skeleton": self.context.peripheral_context
            }
        else:
            # Fallback or future expansion
            return {"module_3_context": "none"}