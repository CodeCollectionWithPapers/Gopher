import json
import argparse
import sys
import importlib.util
from pathlib import Path

def load_module_from_path(module_name: str, file_path: str):

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def run_tests(bug_id: str, algo_file: str, test_json_dir: str):

    json_path = Path(test_json_dir) / f"{bug_id}.json"
    if not json_path.exists():
        print(f"Error: Test cases not found at {json_path}")
        sys.exit(1)

    with open(json_path, 'r') as f:
        test_cases = json.load(f)

    try:
        module = load_module_from_path(bug_id, algo_file)
        func = getattr(module, bug_id)
    except Exception as e:
        print(f"Error loading module: {e}")
        sys.exit(1)

    failed = 0
    passed = 0

    for i, test in enumerate(test_cases):
        inputs = test["input"]
        expected = test["output"]

        try:
            if isinstance(inputs, list):
                result = func(*inputs)
            else:
                result = func(inputs)

            if result == expected:
                passed += 1
            else:
                print(f"FAIL Test {i}: Expected {expected}, got {result}")
                failed += 1
                sys.exit(1)

        except Exception as e:
            print(f"ERROR Test {i}: Exception raised: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print(f"SUCCESS: {passed} tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bug", required=True, help="Bug ID (algorithm name, e.g., quicksort)")
    parser.add_argument("--file", help="")
    parser.add_argument("--json_dir", default="./json_testcases", help="")

    args = parser.parse_args()
    target_file = args.file if args.file else f"{args.bug}.py"
    run_tests(args.bug, target_file, args.json_dir)