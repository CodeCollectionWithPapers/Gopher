from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class PatchStatus(Enum):

    GENERATED = "GENERATED"  # Patch just created by LLM
    COMPILATION_FAILED = "COMPILE_ERR"  # Failed to compile (syntax error)
    TEST_FAILED = "TEST_FAIL"  # Compiled but failed test suite
    PLAUSIBLE = "PLAUSIBLE"  # Passed all trigger tests (potential fix)
    TIMEOUT = "TIMEOUT"  # Execution took too long


@dataclass
class TestResult:
    """Captures the output of the execution/testing module."""
    passed: bool
    error_message: Optional[str] = None
    failed_test_name: Optional[str] = None
    execution_time: float = 0.0

    def to_feedback_string(self) -> str:
        if self.passed:
            return "Tests Passed."
        return (
            f"Error Message:\n{self.error_message}\n"
            f"Failed Test Case: {self.failed_test_name}"
        )

@dataclass
class CandidatePatch:

    bug_id: str
    raw_output: str
    cleaned_code: str
    llm_model: str
    round_number: int
    diff: str = ""
    status: PatchStatus = PatchStatus.GENERATED
    test_result: Optional[TestResult] = None

    def is_plausible(self) -> bool:
        return self.status == PatchStatus.PLAUSIBLE

    def get_identifier(self) -> str:
        return f"{self.bug_id}_{self.llm_model}_round{self.round_number}_{hash(self.cleaned_code)}"