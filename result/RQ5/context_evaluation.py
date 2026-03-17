
import re
import pandas as pd
import tiktoken
import json

try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    import tiktoken
    tokenizer = tiktoken.get_encoding("gpt2")

JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class",
    "const", "continue", "default", "do", "double", "else", "enum", "extends", "final",
    "finally", "float", "for", "goto", "if", "implements", "import", "instanceof", "int",
    "interface", "long", "native", "new", "package", "private", "protected", "public",
    "return", "short", "static", "strictfp", "super", "switch", "synchronized", "this",
    "throw", "throws", "transient", "try", "void", "volatile", "while", "true", "false", "null",
    "Override", "String", "Object"
}


def count_tokens(text) -> int:

    if text is None:
        return 0

    if isinstance(text, list):
        text = "\n".join(text)

    if not isinstance(text, str):
        text = str(text)

    if text.strip() == "":
        return 0

    return len(tokenizer.encode(text))


def extract_ingredients(code_text):

    if code_text is None:
        return set()

    if isinstance(code_text, list):
        code_text = "\n".join(code_text)

    if not isinstance(code_text, str):
        code_text = str(code_text)

    identifiers = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', code_text)

    ingredients = {
        i for i in identifiers
        if i not in JAVA_KEYWORDS
    }

    return ingredients


# ---------------------------------------------------------
# core eval
# ---------------------------------------------------------

def evaluate_metrics(dataset: list) -> pd.DataFrame:

    results = []

    for bug in dataset:

        bug_id = bug.get('bug_id')
        buggy_line = bug.get('buggy_line', '')
        patch_added_lines = bug.get('patch_line', '')

        ingredients_patch_raw = extract_ingredients(patch_added_lines)
        ingredients_buggy_line = extract_ingredients(buggy_line)

        E_patch = ingredients_patch_raw - ingredients_buggy_line

        print(f"Ingredients: Patch: {E_patch}")

        if len(E_patch) == 0:
            continue

        c_class = bug.get('class_context', '')
        c_method = bug.get('method_context', '')
        c_katana = bug.get('katana_context', '')
        c_gopher = bug.get('gopher_context', '')

        if not any((c_class, c_method, c_katana, c_gopher)):
            continue

        tok_class = count_tokens(c_class)
        tok_method = count_tokens(c_method)
        tok_katana = count_tokens(c_katana)
        tok_gopher = count_tokens(c_gopher)

        if tok_class == 0:
            continue

        E_class = extract_ingredients(c_class)
        E_method = extract_ingredients(c_method)
        E_katana = extract_ingredients(c_katana)
        E_gopher = extract_ingredients(c_gopher)

        ir_class = len(E_patch.intersection(E_class)) / len(E_patch)
        ir_method = len(E_patch.intersection(E_method)) / len(E_patch)
        ir_katana = len(E_patch.intersection(E_katana)) / len(E_patch)
        ir_gopher = len(E_patch.intersection(E_gopher)) / len(E_patch)

        print(f"Bug_id:{bug_id}-----,IR: Class: {ir_class}, Method: {ir_method}, Katana: {ir_katana}, Gopher: {ir_gopher}")

        ccr_class = 1.0 - (tok_class / tok_class)
        ccr_method = 1.0 - (tok_method / tok_class)
        ccr_katana = 1.0 - (tok_katana / tok_class)
        ccr_gopher = 1.0 - (tok_gopher / tok_class)

        results.append({
            "Bug_ID": bug_id,
            "Proj": bug_id.split('-')[0],

            "E_patch_size": len(E_patch),

            "Tokens_Class": tok_class,
            "Tokens_Method": tok_method,
            "Tokens_Katana": tok_katana,
            "Tokens_Gopher": tok_gopher,

            "CCR_Method": ccr_method,
            "CCR_Katana": ccr_katana,
            "CCR_Gopher": ccr_gopher,

            "IR_Class": ir_class,
            "IR_Method": ir_method,
            "IR_Katana": ir_katana,
            "IR_Gopher": ir_gopher
        })

    df = pd.DataFrame(results)
    return df

def aggregate_and_print_table(df: pd.DataFrame):

    if df.empty:
        print("Dataset is empty or no valid E_patch found.")
        return

    grouped = df.groupby("Proj").agg({
        "Tokens_Class": "mean",
        "Tokens_Method": "mean",
        "Tokens_Katana": "mean",
        "Tokens_Gopher": "mean",
        "CCR_Method": "mean",
        "CCR_Katana": "mean",
        "CCR_Gopher": "mean",
        "IR_Class": "mean",
        "IR_Method": "mean",
        "IR_Katana": "mean",
        "IR_Gopher": "mean"
    }).reset_index()

    overall = pd.DataFrame({
        "Proj": ["Overall"],
        "Tokens_Class": [df["Tokens_Class"].mean()],
        "Tokens_Method": [df["Tokens_Method"].mean()],
        "Tokens_Katana": [df["Tokens_Katana"].mean()],
        "Tokens_Gopher": [df["Tokens_Gopher"].mean()],
        "CCR_Method": [df["CCR_Method"].mean()],
        "CCR_Katana": [df["CCR_Katana"].mean()],
        "CCR_Gopher": [df["CCR_Gopher"].mean()],
        "IR_Class": [df["IR_Class"].mean()],
        "IR_Method": [df["IR_Method"].mean()],
        "IR_Katana": [df["IR_Katana"].mean()],
        "IR_Gopher": [df["IR_Gopher"].mean()]
    })

    final_df = pd.concat([grouped, overall], ignore_index=True)

    print("=" * 90)
    print(f"{'Project':<15} | {'Strategy':<15} | {'Avg. Tokens':<12} | {'CCR_class (%)':<15} | {'IR (%)':<15}")
    print("-" * 90)

    for _, row in final_df.iterrows():

        proj = row['Proj']

        print(
            f"{proj:<15} | {'Class-Level':<15} | {row['Tokens_Class']:<12.1f} | {'0.0%':<15} | {row['IR_Class'] * 100:<.1f}%")

        print(
            f"{'':<15} | {'Method-Level':<15} | {row['Tokens_Method']:<12.1f} | {row['CCR_Method'] * 100:<.1f}%{'':<10} | {row['IR_Method'] * 100:<.1f}%")

        print(
            f"{'':<15} | {'Katana':<15} | {row['Tokens_Katana']:<12.1f} | {row['CCR_Katana'] * 100:<.1f}%{'':<10} | {row['IR_Katana'] * 100:<.1f}%")

        print(
            f"{'':<15} | {'Gopher (Ours)':<15} | {row['Tokens_Gopher']:<12.1f} | {row['CCR_Gopher'] * 100:<.1f}%{'':<10} | {row['IR_Gopher'] * 100:<.1f}%")

        print("-" * 90)

# ---------------------------------------------------------
# run runr run
# ---------------------------------------------------------

if __name__ == "__main__":

    print("Running evaluation on dataset...")

    file_path = "Here! your_context_data_path" //context_qal_eval

    with open(file_path, "r", encoding="utf-8") as f:
        data_set = json.load(f)

    df_results = evaluate_metrics(data_set)

    aggregate_and_print_table(df_results)
