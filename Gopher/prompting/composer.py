import logging
import yaml
import os
from typing import Dict, Any, Optional, List
from jinja2 import Template, Environment, BaseLoader

from Gopher.core.artifact import BuggyArtifact, DualLayerContext, RepairSession
from Gopher.core.patch import TestResult
from Gopher.LLM.token_manager import TokenManager

logger = logging.getLogger(__name__)


class PromptComposer:
    def __init__(self, config_path: str, token_manager: TokenManager):

        self.token_manager = token_manager
        self.templates = self._load_templates(config_path)
        self.env = Environment(loader=BaseLoader())

    def _load_templates(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt template file not found: {path}")

        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def construct_prompt(self,
                         session: RepairSession,
                         round_num: int,
                         test_result: Optional[TestResult] = None) -> str:

        artifact = session.artifact
        context = session.context

        mod_leading_cfg = self.templates["modules"]["leading"]
        leading_text = (
            f"{mod_leading_cfg['system_message']}\n\n"
            f"{mod_leading_cfg['user_instruction']}"
        )

        mod_artifact_tmpl = self.env.from_string(self.templates["modules"]["buggy_artifact"])
        buggy_code_text = mod_artifact_tmpl.render(
            file_path=artifact.file_path,
            method_name=artifact.method_name,
            language=artifact.language,
            buggy_method_body=artifact.source_code,
            bug_line_number=artifact.buggy_line_no
        )

        mod_context_cfg = self.templates["modules"]["context"]

        if round_num == 1:
            context_tmpl_str = mod_context_cfg["none"] # init: No context
            context_vars = {}

        elif round_num == 2:
            context_tmpl_str = mod_context_cfg["slice"]
            context_vars = {
                "language": artifact.language,
                "data_dependency_slice": context.data_dependency_slice or "(None)",
                "control_dependency_slice": context.control_dependency_slice or "(None)"
            }

        elif round_num == 3:
            context_tmpl_str = mod_context_cfg["periphery"]
            context_vars = {
                "language": artifact.language,
                "class_skeleton": context.peripheral_context or "(None)"
            }
        else:
            context_tmpl_str = mod_context_cfg["none"] # Fallback
            context_vars = {}

        context_text = self.env.from_string(context_tmpl_str).render(**context_vars)

        mod_feedback_cfg = self.templates["modules"]["test_feedback"]

        if test_result and not test_result.passed:
            feedback_tmpl_str = mod_feedback_cfg["failure"]
            feedback_vars = {
                "error_message": test_result.error_message,
                "failed_test_name": test_result.failed_test_name
            }
        else:
            feedback_tmpl_str = mod_feedback_cfg["initial"]
            feedback_vars = {
                "issue_description": "The code fails the provided test suite. Please analyze dependencies and fix it."
            }

        feedback_text = self.env.from_string(feedback_tmpl_str).render(**feedback_vars)

        mod_trailing_tmpl = self.env.from_string(self.templates["modules"]["trailing"])
        trailing_text = mod_trailing_tmpl.render(language=artifact.language)

        static_parts = [
            leading_text,
            "--------------------------------------------------",
            buggy_code_text,
            "--------------------------------------------------",
            trailing_text
        ]

        optimized_context = self.token_manager.optimize_prompt(
            static_parts=static_parts,
            dynamic_context=context_text,
            feedback_part=feedback_text
        )

        full_prompt = (
            f"{leading_text}\n\n"
            f"{buggy_code_text}\n\n"
            f"{optimized_context}\n\n"
            f"{feedback_text}\n\n"
            f"{trailing_text}"
        )

        if not self.token_manager.check_fit(full_prompt):
            # logger.warning("Prompt is still too long after optimization. Forcing drastic truncation.")
            full_prompt = (
                f"{leading_text}\n\n"
                f"{buggy_code_text}\n\n"
                "(Context removed due to extreme length)\n\n"
                f"{feedback_text}\n\n"
                f"{trailing_text}"
            )

        return full_prompt