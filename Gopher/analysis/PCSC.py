import logging
import json
from typing import List, Dict, Set, Optional

from Gopher.core.artifact import BuggyArtifact
from Gopher.analysis.CPG_joern import JoernBridge

logger = logging.getLogger(__name__)

class PeripheralContextExtractor:

    def __init__(self, joern_bridge: JoernBridge):
        self.joern = joern_bridge

        self.skeleton_script = self.joern.config.get("joern", {}).get("scripts", {}).get(
            "ast_extraction", "./src/gopher/analysis/scala/ast_structure.sc"
        )

    def generate_context(self, cpg_path: str, artifact: BuggyArtifact) -> str:

        if not cpg_path:
            logger.error("CPG path is missing. Cannot generate peripheral context.")
            return ""
        params = {
            "filename": artifact.file_path
        }

        try:
            raw_output = self.joern.execute_query_script(cpg_path, self.skeleton_script, params)
            ranges_to_hide = self._parse_ranges(raw_output)

            logger.info(f"Identified {len(ranges_to_hide)} blocks to collapse for peripheral context.")

        except Exception as e:
            logger.error(f"Failed to query AST structure via Joern: {e}")
            return artifact.source_code

        skeleton_code = self._create_skeleton(artifact.source_code, ranges_to_hide)

        return skeleton_code

    def _parse_ranges(self, raw_output: str) -> List[Dict[str, int]]:
        # """
        # Expected Format:
        # [
        #     {"startLine": 10, "endLine": 15},
        #     {"startLine": 20, "endLine": 30}
        # ]
        # """
        ranges = []
        if not raw_output:
            return ranges

        lines = raw_output.strip().splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                try:
                    data = json.loads(line)
                    if isinstance(data, list):
                        for item in data:
                            start = item.get("startLine") or item.get("start")
                            end = item.get("endLine") or item.get("end")
                            if start and end:
                                ranges.append({"start": int(start), "end": int(end)})
                        return ranges
                except json.JSONDecodeError:
                    continue

        logger.warning("No valid JSON ranges found in Joern output for skeleton generation.")
        return ranges

    def _create_skeleton(self, source_code: str, ranges_to_hide: List[Dict[str, int]]) -> str:

        if not ranges_to_hide:
            return source_code

        lines = source_code.splitlines()

        lines_to_suppress = set()
        placeholder_insertion_points = {}

        for rng in ranges_to_hide:
            start = rng["start"]
            end = rng["end"]

            # if end >= start:
            if end > start:
                for i in range(start + 1, end):
                    lines_to_suppress.add(i - 1)

                if start + 1 < end:
                    placeholder_insertion_points[start] = True

        result_lines = []
        for i, line in enumerate(lines):
            if i in lines_to_suppress:
                continue
            result_lines.append(line)

            for rng in ranges_to_hide:
                if (i == rng["start"] - 1) and (rng["end"] > rng["start"]):
                    indent = ""
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        indent = next_line[:len(next_line) - len(next_line.lstrip())]

                    result_lines.append(f"{indent}# ... existing code ...")
                    break

        return "\n".join(result_lines)