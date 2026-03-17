import logging
import re
import json
import time
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any

from Gopher.core.artifact import BuggyArtifact, RepairSession, DualLayerContext
from Gopher.core.patch import CandidatePatch, PatchStatus, TestResult


from Gopher.analysis.CPG_joern import JoernBridge
from Gopher.analysis.dual_layer_conetxt import ContextBuilder
from Gopher.LLM.client import LLMFactory
from Gopher.LLM.token_manager import TokenManager
from Gopher.prompting.composer import PromptComposer
from Gopher.execution.file_manager import FileManager
from Gopher.execution.container import DockerContainerManager
from Gopher.execution.test_runner import TestRunner

logger = logging.getLogger(__name__)


class GopherWorkflow:

    def __init__(self, config_path: str = "configs/settings.yaml"):

        self.config = self._load_config(config_path)
        self.workspace_root = Path(self.config.get("project", {}).get("workspace_root", "./data/workspace"))

        self.joern = JoernBridge(config_path)
        self.context_builder = ContextBuilder(self.joern)

        default_provider = "openai"
        self.llm_client = LLMFactory.create_client(default_provider, config_path)
        self.token_manager = TokenManager(self.llm_client.model_name)

        self.composer = PromptComposer("configs/prompt_templates.yaml", self.token_manager)

        self.file_manager = FileManager(str(self.workspace_root))
        self.container_cfg = self.config.get("datasets", {})

        self.max_rounds = self.config.get("strategy", {}).get("max_iterations", 3)

    def _load_config(self, path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def run_repair(self, artifact: BuggyArtifact, dataset_type: str = "defects4j"):

        logger.info(f"Starting repair session for {artifact.identifier}...")

        self.file_manager.backup_file(artifact.file_path)

        logger.info("Step 1: Generatring Code Property Graph (CPG)...")
        cpg_dir = self.workspace_root / "cpgs" / artifact.identifier
        try:
            cpg_path = self.joern.generate_cpg(artifact, str(cpg_dir))

            logger.info("Step 2: Building Dual-Layer Context...")

            ddg_slice, cdg_slice = self.context_builder.slicer.generate_slices(cpg_path, artifact)

            periphery = self.context_builder.periphery.generate_context(cpg_path, artifact)

            context = DualLayerContext(
                data_dependency_slice=ddg_slice,
                control_dependency_slice=cdg_slice,
                peripheral_context=periphery
            )

        except Exception as e:
            logger.error(f"Analysis failed: {e}. Proceeding with empty context.")
            context = DualLayerContext()
        session = RepairSession(
            artifact=artifact,
            context=context,
            workspace_dir=str(self.workspace_root)
        )

        last_test_result: Optional[TestResult] = None
        project_root = str(Path(artifact.file_path).parent.parent.parent)
        volumes = {project_root: {'bind': '/workspace', 'mode': 'rw'}}

        image_name = "defects4j-env" if dataset_type == "defects4j" else "python:3.9"
        container_mgr = DockerContainerManager(image_name)

        with container_mgr.provision_container(volumes=volumes) as container:
            test_runner = TestRunner(self.config, container_mgr)

            for round_num in range(1, self.max_rounds + 1):
                logger.info(f"--- Round {round_num}/{self.max_rounds} (Context: {self._get_round_name(round_num)}) ---")
                prompt = self.composer.construct_prompt(session, round_num, last_test_result)
                logger.info("Querying LLM...")
                try:

                    raw_response = self.llm_client.generate_completion(
                        system_message="You are an expert automated program repair agent.",
                        user_prompt=prompt
                    )
                except Exception as e:
                    logger.error(f"LLM Generation failed: {e}")
                    continue

                code_block = self._extract_code_block(raw_response)
                if not code_block:
                    logger.warning("No code block found in LLM response.")
                    last_test_result = TestResult(passed=False, error_message="LLM did not return a valid code block.")
                    continue

                patch = CandidatePatch(
                    bug_id=artifact.bug_id,
                    raw_output=raw_response,
                    cleaned_code=code_block,
                    llm_model=self.llm_client.model_name,
                    round_number=round_num
                )

                logger.info("Validating Patch...")

                try:
                    self.file_manager.write_patch(artifact.file_path, patch.cleaned_code)
                    patch.diff = self.file_manager.compute_diff(
                        artifact.source_code, patch.cleaned_code, artifact.file_path
                    )
                except Exception as e:
                    logger.error(f"Failed to apply patch: {e}")
                    patch.status = PatchStatus.COMPILATION_FAILED
                    last_test_result = TestResult(passed=False, error_message=f"File write error: {e}")
                    self._record_patch(patch)
                    continue

                result = test_runner.run_tests(artifact, container)
                patch.test_result = result
                last_test_result = result

                if result.passed:
                    logger.info(f"SUCCESS! Patch found in Round {round_num}.")
                    patch.status = PatchStatus.PLAUSIBLE
                    self._record_patch(patch, success=True)

                    self.file_manager.restore_file(artifact.file_path)
                    return True
                else:
                    logger.info(f"Patch failed: {result.error_message[:100]}...")
                    patch.status = PatchStatus.TEST_FAILED
                    self._record_patch(patch, success=False)

                    self.file_manager.restore_file(artifact.file_path)

        logger.info(f"Repair session finished. No fix found after {self.max_rounds} rounds.")
        self.file_manager.restore_file(artifact.file_path)  # Final cleanup
        return False

    def _extract_code_block(self, text: str) -> Optional[str]:
        pass