def write_to_file(filename: str, data: str) -> None:
    """
    Writes the given string data to a file.

    Args:
        filename (str): Name or path of the file.
        data (str): String content to write into the file.
    """
    with open(filename, "w", encoding="utf-8") as file:
        file.write(data)


import os
def delete_file(filename: str) -> None:
    """
    Deletes the specified file.

    Args:
        filename (str): Name or path of the file to delete.
    """
    if os.path.exists(filename):
        os.remove(filename)
        print(f"File '{filename}' deleted successfully.")
    else:
        print(f"File '{filename}' does not exist.")

