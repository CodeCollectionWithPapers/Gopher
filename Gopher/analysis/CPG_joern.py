import os
import subprocess
import logging
import yaml
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import core definitions
from Gopher.core.artifact import BuggyArtifact

logger = logging.getLogger(__name__)


class JoernBridge:

    def __init__(self, config_path: str = "configs/settings.yaml"):

        self.config = self._load_config(config_path)
        self.joern_config = self.config.get("joern", {})

        self.joern_bin = self.joern_config.get("installation_path", "/usr/bin")
        self.jvm_opts = self.joern_config.get("java_opts", "-Xmx8g")

        self._check_installation()

    def _load_config(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            logger.warning(f"Config file not found at {path}, using defaults.")
            return {}
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _check_installation(self):
        # Check specific commands we need
        parse_cmd = self.joern_config.get("parse_command", "joern-parse")

        if not shutil.which(parse_cmd):
            # Try combining with installation_path
            potential_path = os.path.join(self.joern_bin, parse_cmd)
            if os.path.exists(potential_path):
                self.joern_bin = str(Path(potential_path).parent)
            else:
                logger.warning(f"Joern command '{parse_cmd}' not found in PATH or {self.joern_bin}. Analysis may fail.")

    def generate_cpg(self, artifact: BuggyArtifact, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)

        cpg_path = os.path.join(output_dir, "cpg.bin")

        project_root = str(Path(artifact.file_path).parent)  # This might need adjustment based on dataset structure

        logger.info(f"Generating CPG for project at: {project_root}")

        cmd = [
            self.joern_config.get("parse_command", "joern-parse"),
            project_root,
            "--language", artifact.language,
            "--output", cpg_path
        ]

        env = os.environ.copy()
        env["JAVA_OPTS"] = self.jvm_opts

        timeout = self.joern_config.get("timeouts", {}).get("cpg_generation", 600)

        try:
            self._run_command(cmd, env=env, timeout=timeout)

            if not os.path.exists(cpg_path):
                raise RuntimeError(f"CPG file was not created at {cpg_path}")

            logger.info(f"CPG successfully generated at {cpg_path}")
            return cpg_path

        except subprocess.TimeoutExpired:
            logger.error(f"CPG generation timed out after {timeout} seconds.")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Joern parse failed: {e.stderr}")
            raise RuntimeError("Joern parse command failed.") from e

    def generate_graph_representations(self, cpg_path: str, output_dir: str):
        export_cmd = self.joern_config.get("export_command", "joern-export")

        # Representations to export
        reprs = ["ast", "pdg", "cdg"]

        for repr_type in reprs:
            out_file = os.path.join(output_dir, f"{repr_type}.dot")
            cmd = [
                export_cmd,
                cpg_path,
                "--repr", repr_type,
                "--out", out_file
            ]

            try:
                logger.info(f"Exporting {repr_type} graph to {out_file}...")
                self._run_command(cmd, timeout=300)
            except Exception as e:
                logger.warning(f"Failed to export {repr_type}: {e}")

    def execute_query_script(self, cpg_path: str, script_path: str, params: Dict[str, str] = None) -> str:
        if params is None:
            params = {}

        params["cpgFile"] = cpg_path
        param_args = []
        for k, v in params.items():
            param_args.extend([f"--param", f"{k}={v}"])

        cmd = [
                  self.joern_config.get("cli_command", "joern"),
                  "--script", script_path
              ] + param_args

        env = os.environ.copy()
        env["JAVA_OPTS"] = self.jvm_opts

        timeout = self.joern_config.get("timeouts", {}).get("script_execution", 300)

        logger.info(f"Executing Scala script: {script_path} with params {params}")

        result = self._run_command(cmd, env=env, timeout=timeout, capture_output=True)
        return result.stdout

    def _run_command(self, cmd: List[str], env: Dict = None, timeout: int = 600, capture_output: bool = False):

        if env is None:
            env = os.environ.copy()

        logger.debug(f"Running command: {' '.join(cmd)}")

        run_args = {
            "env": env,
            "timeout": timeout,
            "check": True,
            "text": True
        }

        if capture_output:
            run_args["stdout"] = subprocess.PIPE
            run_args["stderr"] = subprocess.PIPE
        else:
            run_args["stdout"] = subprocess.PIPE
            run_args["stderr"] = subprocess.PIPE

        try:
            result = subprocess.run(cmd, **run_args)
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with return code {e.returncode}")
            if e.stdout:
                logger.error(f"STDOUT: {e.stdout}")
            if e.stderr:
                logger.error(f"STDERR: {e.stderr}")
            raise