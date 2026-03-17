import logging
from typing import Set, List, Dict

from Gopher.core.artifact import BuggyArtifact
from Gopher.analysis.CPG_joern import JoernBridge
from Gopher.analysis.FDS import FocusedSlicer
from Gopher.analysis.PCSC import PeripheralContextExtractor

logger = logging.getLogger(__name__)


class ContextBuilder:

    def __init__(self, joern_bridge: JoernBridge):
        self.joern = joern_bridge
        self.slicer = FocusedSlicer(joern_bridge)
        self.periphery = PeripheralContextExtractor(joern_bridge)

    def build_mixed_context(self, cpg_path: str, artifact: BuggyArtifact) -> str:

        if not cpg_path:
            logger.error("Invalid CPG path.")
            return artifact.source_code

        slice_params = {
            "filename": artifact.file_path,
            "lineNumber": str(artifact.buggy_line_no)
        }
        if artifact.method_name:
            slice_params["methodName"] = artifact.method_name

        ddg_lines = self.slicer._run_slicing_strategy(
            cpg_path, self.slicer.ddg_script_path, slice_params, "Data"
        )
        cdg_lines = self.slicer._run_slicing_strategy(
            cpg_path, self.slicer.cdg_script_path, slice_params, "Control"
        )

        slice_lines_set = ddg_lines.union(cdg_lines)
        slice_lines_set.add(artifact.buggy_line_no)

        periphery_params = {"filename": artifact.file_path}
        raw_ast_output = self.joern.execute_query_script(
            cpg_path, self.periphery.skeleton_script, periphery_params
        )
        ranges_to_hide = self.periphery._parse_ranges(raw_ast_output)

        return self._stitch_code(artifact.source_code, slice_lines_set, ranges_to_hide)

    def _stitch_code(self, source_code: str, slice_lines: Set[int], ranges_to_hide: List[Dict[str, int]]) -> str:

        lines = source_code.splitlines()
        stitched_lines = []

        is_suppressible = [False] * len(lines)

        for rng in ranges_to_hide:
            start = rng["start"]
            end = rng["end"]

            if end > start:
                for i in range(start + 1, end):  # 1-based logic from Joern
                    idx = i - 1  # 0-based
                    if 0 <= idx < len(lines):
                        is_suppressible[idx] = True

        last_was_gap = False

        for i, line_content in enumerate(lines):
            line_num = i + 1

            should_keep = True

            if is_suppressible[i]:

                if line_num in slice_lines:
                    should_keep = True
                else:
                    should_keep = False

            if should_keep:
                stitched_lines.append(line_content)
                last_was_gap = False
            else:
                if not last_was_gap:
                    indent = line_content[:len(line_content) - len(line_content.lstrip())]
                    stitched_lines.append(f"{indent}# ... (irrelevant code hidden)")
                    last_was_gap = True

        return "\n".join(stitched_lines)