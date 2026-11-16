import pandas as pd
import requests
import json
import re
from import_credential import SPREADSHEET_ID, EM7_GID, TEACHERS_OPINION_GID


def lab_data(section: str, student_name: str = None, teachers_eval: bool = None) -> str:
    """
    Fetch lab result data from Google Sheets for a given class section
    using the gviz JSON API, which guarantees all columns are returned.
    Optionally filter by student name using partial, case-insensitive matching.

    Args:
        section: The class section name, either '7em' or '6cm'.
        student_name: Optional student name to search for (partial match supported).

    Returns:
        A string representation of the matching student(s) data, or the full sheet.
    """

    # Determine correct GID based on priority
    if teachers_eval is True:
        gid = TEACHERS_OPINION_GID
    elif section.lower() == "7em":
        gid = EM7_GID
    else:
        gid = "0"

    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        f"/gviz/tq?tqx=out:json&gid={gid}"
    )

    response = requests.get(url)
    response.raise_for_status()

    raw = response.text
    match = re.search(r"google\.visualization\.Query\.setResponse\((.*)\);", raw, re.DOTALL)
    if not match:
        raise ValueError("Unexpected response format from Google Sheets gviz API.")

    data = json.loads(match.group(1))
    table = data["table"]

    # Extract column headers
    columns = []
    for i, col in enumerate(table["cols"]):
        label = (col.get("label") or col.get("id") or "").strip()
        # If label is empty, name it by index so it doesn't get silently lost
        columns.append(label if label else f"_col_{i}")

    # Extract rows
    rows = []
    for row in table["rows"]:
        if row is None:
            rows.append([None] * len(columns))
            continue
        values = []
        for cell in row["c"]:
            if cell is None:
                values.append(None)
            else:
                values.append(cell.get("v"))
        rows.append(values)

    df = pd.DataFrame(rows, columns=columns)

    # ── DEBUG: print every column name and shape ──────────────────────────────
    # print("Shape:", df.shape)
    # print("All columns:", df.columns.tolist())
    # ─────────────────────────────────────────────────────────────────────────

    # Drop only fully empty ROWS — do NOT drop columns blindly
    df.dropna(how="all", axis=0, inplace=True)

    # Drop only columns that have an auto-generated placeholder name AND are empty
    placeholder_cols = [c for c in df.columns if c.startswith("_col_") and df[c].isna().all()]
    df.drop(columns=placeholder_cols, inplace=True)
    # print(df)
    # Optional: filter by student name
    if student_name:
        if "Name" not in df.columns:
            return f"'Name' column not found. Available columns: {df.columns.tolist()}"

        name_lower = student_name.lower()
        mask = df["Name"].str.lower().str.contains(name_lower, na=False)
        result = df[mask]

        if result.empty:
            return f"No student found matching '{student_name}' in section {section.upper()}."

        return result.to_string(index=False)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)
    return df.to_string(index=False)
