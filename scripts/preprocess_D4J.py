import os
import json
import subprocess
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_cmd(cmd: str, cwd: str = ".") -> str:
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nStderr: {result.stderr}")
    return result.stdout.strip()


def parse_d4j_info(info_text: str, project_root: str) -> Dict[str, Any]:

    src_dir_cmd = "defects4j export -p dir.src.classes"
    src_dir = run_cmd(src_dir_cmd, cwd=project_root)

    mod_classes_cmd = "defects4j export -p classes.modified"
    mod_classes_str = run_cmd(mod_classes_cmd, cwd=project_root)
    modified_classes = mod_classes_str.split("::") if "::" in mod_classes_str else [mod_classes_str]

    target_class = modified_classes[0]

    rel_file_path = target_class.replace(".", "/") + ".java"
    full_file_path = os.path.join(src_dir, rel_file_path)

    return {
        "src_root": src_dir,
        "rel_file_path": rel_file_path,
        "full_file_path": full_file_path,
        "class_name": target_class
    }

def get_buggy_line(project_root: str, file_path: str) -> int:
    # info_cmd = "defects4j export -p classes.modified"
    # info_text = run_cmd(info_cmd, cwd=project_root)
    return 0

def process_bug(project: str, bug_id: str, output_dir: Path) -> Dict[str, Any]:
    work_dir = output_dir / "checkout" / f"{project}_{bug_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Checking out {project}-{bug_id}b...")
    run_cmd(f"defects4j checkout -p {project} -v {bug_id}b -w {work_dir}")

    try:
        meta = parse_d4j_info("", str(work_dir))

        abs_file_path = work_dir / meta["full_file_path"]
        if not abs_file_path.exists():
            logger.warning(f"File not found: {abs_file_path}")
            return None

        with open(abs_file_path, 'r', encoding='utf-8', errors='replace') as f:
            source_code = f.read()

        artifact = {
            "project_name": project,
            "bug_id": bug_id,
            "file_path": str(abs_file_path.resolve()),
            "method_name": "unknown_method",
            "buggy_line_no": 0,
            "source_code": source_code,
            "language": "java"
        }

        return artifact

    except Exception as e:
        logger.error(f"Failed to process {project}-{bug_id}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Preprocess Defects4J bugs for Gopher.")
    parser.add_argument("--output_dir", required=True, help="Directory to save artifacts")
    parser.add_argument("--project", required=True, help="Project name (e.g., Chart)")
    parser.add_argument("--ids", required=True, help="Bug IDs (e.g., 1,2,3 or 1-10)")

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bug_ids = []
    if "-" in args.ids:
        start, end = map(int, args.ids.split("-"))
        bug_ids = [str(i) for i in range(start, end + 1)]
    else:
        bug_ids = args.ids.split(",")

    artifacts = []
    for bid in bug_ids:
        art = process_bug(args.project, bid, output_dir)
        if art:
            artifacts.append(art)

    manifest_path = output_dir / f"{args.project}_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(artifacts, f, indent=4)

    logger.info(f"Saved {len(artifacts)} artifacts to {manifest_path}")

if __name__ == "__main__":
    main()