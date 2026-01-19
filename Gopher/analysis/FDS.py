import json
import logging
from typing import List, Dict, Tuple, Optional, Set

from Gopher.core.artifact import BuggyArtifact
from Gopher.analysis.CPG_joern import JoernBridge

logger = logging.getLogger(__name__)

class FocusedSlicer:

    def __init__(self, joern_bridge: JoernBridge):
        self.joern = joern_bridge

        scripts_config = self.joern.config.get("joern", {}).get("scripts", {})
        self.ddg_script_path = scripts_config.get(
            "data_dep_slice", "./src/gopher/analysis/scala/data_dependency.sc"
        )
        self.cdg_script_path = scripts_config.get(
            "control_dep_slice", "./src/gopher/analysis/scala/control_dependency.sc"
        )

    def generate_slices(self, cpg_path: str, artifact: BuggyArtifact) -> Tuple[str, str]:

        if not cpg_path:
            logger.error("CPG path is empty. Cannot perform slicing.")
            return "", ""

        params = {
            "filename": artifact.file_path,
            "lineNumber": str(artifact.buggy_line_no)
        }

        if artifact.method_name:
            params["methodName"] = artifact.method_name
        else:
            logger.warning(f"Method name missing for bug {artifact.buggy_id}. Slicing based on line number only.")

        ddg_lines = self._run_slicing_strategy(
            cpg_path,
            self.ddg_script_path,
            params,
            slice_type="Data"
        )

        cdg_lines = self._run_slicing_strategy(
            cpg_path,
            self.cdg_script_path,
            params,
            slice_type="Control"
        )

        source_code_lines = artifact.source_code.splitlines()

        ddg_code_block = self._construct_code_block(source_code_lines, ddg_lines)
        cdg_code_block = self._construct_code_block(source_code_lines, cdg_lines)

        return ddg_code_block, cdg_code_block

    def _run_slicing_strategy(
            self,
            cpg_path: str,
            script_path: str,
            params: Dict[str, str],
            slice_type: str
    ) -> Set[int]:

        logger.info(f"Running {slice_type} Dependency Slicing...")

        try:
            raw_output = self.joern.execute_query_script(cpg_path, script_path, params)
            parsed_lines = self._parse_joern_list_output(raw_output)

            logger.info(f"Found {len(parsed_lines)} relevant lines for {slice_type} slice.")
            return parsed_lines

        except Exception as e:
            logger.error(f"Failed to generate {slice_type} slice: {e}")
            return set()

    def _parse_joern_list_output(self, raw_output: str) -> Set[int]:

        if not raw_output:
            return set()
        lines = raw_output.strip().splitlines()

        for line in reversed(lines):
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                try:
                    data = json.loads(line)
                    if isinstance(data, list):
                        # Convert to unique set of integers, filter out Nones
                        return {int(x) for x in data if x is not None}
                except json.JSONDecodeError:
                    continue

        # logger.warning("Could not find valid JSON list in Joern output.")
        logger.debug(f"Raw Output: {raw_output}")
        return set()

    def _construct_code_block(self, source_lines: List[str], line_numbers: Set[int]) -> str:

        if not line_numbers:
            return "(No dependencies found or slicing failed)"

        sorted_lines = sorted(list(line_numbers))
        reconstructed = []

        max_line_index = len(source_lines) - 1

        for line_no in sorted_lines:
            idx = line_no - 1
            if 0 <= idx <= max_line_index:
                code_content = source_lines[idx]
                reconstructed.append(code_content)
            else:
                logger.debug(f"Slice line number {line_no} out of bounds for source file.")

        return "\n".join(reconstructed)