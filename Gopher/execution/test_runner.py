import logging
import re
import time
from typing import Dict, Any, Optional
from Gopher.core.patch import TestResult
from Gopher.core.artifact import BuggyArtifact
from Gopher.execution.container import DockerContainerManager

logger = logging.getLogger(__name__)

class TestRunner:

    def __init__(self, config: Dict[str, Any], container_manager: DockerContainerManager):

        self.config = config
        self.container_manager = container_manager
        self.datasets_config = config.get("datasets", {})
        self.d4j_projects = {
            "Chart", "Cli", "Closure", "Codec", "Collections", "Compress",
            "Csv", "Gson", "JacksonCore", "JacksonDatabind", "JacksonXml",
            "Jsoup", "JxPath", "Lang", "Math", "Mockito", "Time"
        }
        # L = ['Chart-1', 'Chart-10', 'Chart-11', 'Chart-12', 'Chart-13', 'Chart-17', 'Chart-20', 'Chart-24', 'Chart-26',
        #      'Chart-3', 'Chart-4', 'Chart-5', 'Chart-6', 'Chart-7', 'Chart-8', 'Chart-9',
        #      'Closure-1', 'Closure-10', 'Closure-101', 'Closure-102', 'Closure-104', 'Closure-105', 'Closure-107',
        #      'Closure-109', 'Closure-11', 'Closure-111', 'Closure-112', 'Closure-113', 'Closure-114', 'Closure-115',
        #      'Closure-116', 'Closure-117', 'Closure-118', 'Closure-119', 'Closure-12', 'Closure-120', 'Closure-121',
        #      'Closure-122', 'Closure-123', 'Closure-124', 'Closure-125', 'Closure-126', 'Closure-128', 'Closure-129',
        #      'Closure-13', 'Closure-130', 'Closure-131', 'Closure-132', 'Closure-133', 'Closure-14', 'Closure-15',
        #      'Closure-17', 'Closure-18', 'Closure-19', 'Closure-2', 'Closure-20', 'Closure-21', 'Closure-22', 'Closure-23',
        #      'Closure-24', 'Closure-25', 'Closure-29', 'Closure-31', 'Closure-32', 'Closure-33', 'Closure-35', 'Closure-36',
        #      'Closure-38', 'Closure-39', 'Closure-4', 'Closure-40', 'Closure-42', 'Closure-44', 'Closure-48', 'Closure-5',
        #      'Closure-50', 'Closure-51', 'Closure-52', 'Closure-53', 'Closure-55', 'Closure-56', 'Closure-57', 'Closure-58',
        #      'Closure-59', 'Closure-61', 'Closure-62', 'Closure-65', 'Closure-66', 'Closure-67', 'Closure-69', 'Closure-7',
        #      'Closure-70', 'Closure-71', 'Closure-73', 'Closure-77', 'Closure-78', 'Closure-81', 'Closure-82', 'Closure-83',
        #      'Closure-86', 'Closure-87', 'Closure-88', 'Closure-91', 'Closure-92', 'Closure-94', 'Closure-95', 'Closure-96',
        #      'Closure-97', 'Closure-99',
        #      'Lang-1', 'Lang-10', 'Lang-11', 'Lang-12', 'Lang-14', 'Lang-16', 'Lang-17', 'Lang-18', 'Lang-19', 'Lang-21',
        #      'Lang-22', 'Lang-24', 'Lang-26', 'Lang-27', 'Lang-28', 'Lang-29', 'Lang-3', 'Lang-31', 'Lang-33', 'Lang-37',
        #      'Lang-38', 'Lang-39', 'Lang-40', 'Lang-42', 'Lang-43', 'Lang-44', 'Lang-45', 'Lang-48', 'Lang-49', 'Lang-5',
        #      'Lang-51', 'Lang-52', 'Lang-53', 'Lang-54', 'Lang-55', 'Lang-57', 'Lang-58', 'Lang-59', 'Lang-6', 'Lang-61',
        #      'Lang-65', 'Lang-9',
        #      'Math-10', 'Math-101', 'Math-102', 'Math-103', 'Math-105', 'Math-106', 'Math-11', 'Math-13', 'Math-17',
        #      'Math-19', 'Math-2', 'Math-20', 'Math-21', 'Math-23', 'Math-24', 'Math-25', 'Math-26', 'Math-27', 'Math-28',
        #      'Math-3', 'Math-30', 'Math-31', 'Math-32', 'Math-33', 'Math-34', 'Math-38', 'Math-39', 'Math-40', 'Math-41',
        #      'Math-42', 'Math-43', 'Math-44', 'Math-45', 'Math-48', 'Math-5', 'Math-50', 'Math-51', 'Math-52', 'Math-53',
        #      'Math-55', 'Math-56', 'Math-57', 'Math-58', 'Math-59', 'Math-60', 'Math-63', 'Math-64', 'Math-69', 'Math-7',
        #      'Math-70', 'Math-72', 'Math-73', 'Math-74', 'Math-75', 'Math-78', 'Math-79', 'Math-8', 'Math-80', 'Math-82',
        #      'Math-84', 'Math-85', 'Math-86', 'Math-87', 'Math-88', 'Math-89', 'Math-9', 'Math-90', 'Math-91', 'Math-94',
        #      'Math-95', 'Math-96', 'Math-97',
        #      'Mockito-1', 'Mockito-12', 'Mockito-13', 'Mockito-18', 'Mockito-20', 'Mockito-22', 'Mockito-24', 'Mockito-27',
        #      'Mockito-28', 'Mockito-29', 'Mockito-33', 'Mockito-34', 'Mockito-38', 'Mockito-5', 'Mockito-7', 'Mockito-8',
        #      'Time-14', 'Time-15', 'Time-16', 'Time-17', 'Time-18', 'Time-19', 'Time-20', 'Time-22', 'Time-23', 'Time-24',
        #      'Time-25', 'Time-27', 'Time-4', 'Time-5', 'Time-7', 'Time-8'
        #      ]

    def run_tests(self, artifact: BuggyArtifact, container, timeout: int = 300) -> TestResult:
        start_time = time.time()

        try:
            if artifact.project_name in self.d4j_projects:
                result = self._run_defects4j(artifact, container, timeout)
            elif "minecraft" in artifact.project_name.lower() or "fabric" in artifact.project_name.lower():
                result = self._run_gradle_test(artifact, container, timeout)
            elif "quixbugs" in artifact.project_name.lower():
                result = self._run_quixbugs(artifact, container, timeout)
            else:

                logger.warning(f"Unknown project type for {artifact.project_name}. Attempting generic Gradle.")
                result = self._run_gradle_test(artifact, container, timeout)

        except Exception as e:
            logger.error(f"Test execution exception: {e}")
            result = TestResult(
                passed=False,
                error_message=f"Internal Runner Error: {str(e)}",
                failed_test_name="Infrastructure"
            )

        result.execution_time = time.time() - start_time
        return result

    def _run_defects4j(self, artifact: BuggyArtifact, container, timeout: int) -> TestResult:

        d4j_cfg = self.datasets_config.get("defects4j", {})
        work_dir = f"/workspace/{artifact.project_name}_{artifact.bug_id}"

        compile_cmd = d4j_cfg.get("compile_cmd", "defects4j compile").format(work_dir=work_dir)
        exit_code, stdout, stderr = self.container_manager.exec_command(
            container, compile_cmd, workdir=work_dir, timeout=timeout
        )

        if exit_code != 0:
            return TestResult(
                passed=False,
                error_message=self._clean_compile_error(stderr + stdout),
                failed_test_name="Compilation"
            )

        test_cmd = d4j_cfg.get("test_cmd", "defects4j test").format(work_dir=work_dir)
        exit_code, stdout, stderr = self.container_manager.exec_command(
            container, test_cmd, workdir=work_dir, timeout=timeout
        )

        return self._parse_defects4j_output(stdout, stderr)

    def _parse_defects4j_output(self, stdout: str, stderr: str) -> TestResult:
        if "Failing tests: 0" in stdout:
            return TestResult(passed=True)

        fail_match = re.search(r"Failing tests: (\d+)", stdout)
        if fail_match:
            count = int(fail_match.group(1))

            test_lines = re.findall(r"^\s*-\s+(.*)$", stdout, re.MULTILINE)
            first_test = test_lines[0] if test_lines else "UnknownTest"

            error_msg = f"Defects4J reported {count} failures."
            if stderr:
                error_msg += f"\nOutput:\n{stderr[:1000]}"

            return TestResult(
                passed=False,
                error_message=error_msg,
                failed_test_name=first_test
            )

        return TestResult(
            passed=False,
            error_message=f"Defects4J execution failed unexpectedly:\n{stderr}\n{stdout[:500]}",
            failed_test_name="ExecutionError"
        )

    def _run_gradle_test(self, artifact: BuggyArtifact, container, timeout: int) -> TestResult:

        cmd = "./gradlew test --info"
        exit_code, stdout, stderr = self.container_manager.exec_command(
            container, cmd, workdir="/workspace", timeout=timeout
        )

        if exit_code == 0:
            return TestResult(passed=True)

        return self._parse_gradle_output(stdout, stderr)

    def _parse_gradle_output(self, stdout: str, stderr: str) -> TestResult:

        test_pattern = r"((?:[a-zA-Z_0-9]+\.)+[a-zA-Z_0-9]+)\s+>\s+([a-zA-Z_0-9]+)\s+FAILED"
        match = re.search(test_pattern, stdout)

        failed_test = "UnknownTest"
        if match:
            failed_test = f"{match.group(1)}::{match.group(2)}"

        error_lines = []
        capture = False
        for line in stdout.splitlines():
            if "FAILED" in line and failed_test in line:
                capture = True
            if capture:
                if any(x in line for x in ["Exception", "Error", "at "]):
                    error_lines.append(line.strip())
                if len(error_lines) > 5:  # Limit capture size
                    break

        error_msg = "\n".join(error_lines) if error_lines else "Tests failed (check logs)"

        return TestResult(
            passed=False,
            error_message=error_msg,
            failed_test_name=failed_test
        )

    def _run_quixbugs(self, artifact: BuggyArtifact, container, timeout: int) -> TestResult:

        cmd = f"python3 scripts/run_quixbugs_test.py --bug {artifact.bug_id}"

        exit_code, stdout, stderr = self.container_manager.exec_command(
            container, cmd, workdir="/workspace", timeout=timeout
        )

        if exit_code == 0:
            return TestResult(passed=True)

        return self._parse_python_traceback(stderr + stdout)

    def _parse_python_traceback(self, output: str) -> TestResult:

        lines = output.strip().splitlines()
        if not lines:
            return TestResult(passed=False, error_message="Empty error output", failed_test_name="Unknown")

        last_line = lines[-1]
        return TestResult(
            passed=False,
            error_message=output[-1000:],
            failed_test_name="QuixBugs_Test_Case"
        )

    def _clean_compile_error(self, output: str) -> str:

        lines = [line for line in output.splitlines() if "error:" in line or "Error:" in line]
        if lines:
            return "\n".join(lines[:5])
        return output[-500:]