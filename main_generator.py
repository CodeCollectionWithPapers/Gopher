import argparse
import logging
import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

import colorlog
from tqdm import tqdm

from Gopher.workflow import GopherWorkflow
from Gopher.core.artifact import BuggyArtifact
from Gopher.LLM.client import LLMFactory
from Gopher.LLM.token_manager import TokenManager

def setup_logging(log_level: str = "INFO"):

    logger = logging.getLogger()
    logger.setLevel(log_level.upper())

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level.upper())

    color_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )
    console_handler.setFormatter(color_formatter)
    logger.addHandler(console_handler)

    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler("logs/gopher_execution.log")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

def load_artifacts(manifest_path: str, project_filter: str = None, bug_id_filter: str = None) -> List[BuggyArtifact]:

    path = Path(manifest_path)
    if not path.exists():
        logging.error(f"Manifest file not found: {manifest_path}")
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    artifacts = []
    for item in data:
        if project_filter and item.get("project_name") != project_filter:
            continue
        if bug_id_filter and str(item.get("bug_id")) != str(bug_id_filter):
            continue

        try:
            artifact = BuggyArtifact(
                project_name=item["project_name"],
                bug_id=str(item["bug_id"]),
                file_path=item["file_path"],
                method_name=item.get("method_name", "unknown"),
                buggy_line_no=int(item.get("buggy_line_no", 0)),
                source_code=item["source_code"],
                language=item.get("language", "java")
            )
            artifacts.append(artifact)
        except KeyError as e:
            logging.warning(f"Skipping invalid artifact entry in manifest: Missing {e}")

    return artifacts

def main():
    parser = argparse.ArgumentParser(
        description="LLM-based Automated Program Repair Tool via Dual-Layer Context."
    )

    parser.add_argument(
        "--manifest",
        type=str,
        required=True,
        help="Path to the input manifest JSON (e.g., data/inputs/Chart_manifest.json)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/settings.yaml",
        help="Path to the global configuration file."
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./data/outputs",
        help="Directory to store repair results and patches."
    )

    parser.add_argument("--project", type=str, default=None, help="Filter execution to a specific project")
    parser.add_argument("--bug_id", type=str, default=None, help="Filter execution to a specific bug ID")

    parser.add_argument(
        "--provider",
        type=str,
        help=""
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="defects4j",
        choices=["defects4j", "quixbugs", "minecraft"],
        help="Dataset type to select correct test runner strategy."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging."
    )

    args = parser.parse_args()

    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(log_level)
    logger = logging.getLogger("main")

    logger.info("Initializing Gopher APR Tool...")

    logger.info(f"Loading artifacts from {args.manifest}...")
    artifacts = load_artifacts(args.manifest, args.project, args.bug_id)

    if not artifacts:
        logger.error("No artifacts found matching criteria. Exiting.")
        sys.exit(0)

    logger.info(f"Found {len(artifacts)} bugs to process.")

    try:
        workflow = GopherWorkflow(config_path=args.config)

        if args.provider:

            logger.info(f"Overriding LLM provider to: {args.provider}")
            workflow.llm_client = LLMFactory.create_client(args.provider, args.config)
            workflow.token_manager = TokenManager(workflow.llm_client.model_name)
            workflow.composer.token_manager = workflow.token_manager

    except Exception as e:
        logger.critical(f"Failed to initialize Gopher Workflow: {e}")
        sys.exit(1)

    results = {
        "fixed": [],
        "failed": [],
        "errors": []
    }

    pbar = tqdm(artifacts, desc="Repairing Bugs", unit="bug")

    for artifact in pbar:
        pbar.set_postfix_str(f"Current: {artifact.identifier}")
        logger.info(f"STARTING REPAIR: {artifact.identifier}")

        try:
            is_fixed = workflow.run_repair(artifact, dataset_type=args.dataset)

            if is_fixed:
                results["fixed"].append(artifact.identifier)
                logger.info(f"FIXED: {artifact.identifier}")
            else:
                results["failed"].append(artifact.identifier)
                logger.info(f"FAILED: {artifact.identifier}")

        except KeyboardInterrupt:
            logger.warning("Execution interrupted by user. Saving progress...")
            break
        except Exception as e:
            logger.error(f"Unexpected error processing {artifact.identifier}: {e}", exc_info=True)
            results["errors"].append(artifact.identifier)

    # logger.info("=" * 50)
    logger.info("EXECUTION SUMMARY")
    # logger.info("=" * 50)
    logger.info(f"Total Processed: {len(artifacts)}")
    logger.info(f"Fixed: {len(results['fixed'])}")
    logger.info(f"Failed: {len(results['failed'])}")
    logger.info(f"Errors: {len(results['errors'])}")

    if results["fixed"]:
        logger.info(f"Fixed Bugs: {', '.join(results['fixed'])}")

    summary_path = Path(args.output_dir) / "execution_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=4)

    logger.info(f"Summary saved to {summary_path}")

if __name__ == "__main__":
    main()