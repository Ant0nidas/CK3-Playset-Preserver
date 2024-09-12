import base64
import datetime
import pathlib
import re
import shutil
import sqlite3
from textwrap import dedent
import time
import uuid

from tqdm import tqdm


def display_welcome_message():
    ascii_art = dedent("""\
        &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&% *   ,,*&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&&&&&&(@. *&&&&&&&&&&&         &&&&&&&&&&&&&&&%%%%&&&&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&&      &%&&&&&&&&&&&&         @&&&&&&&&&&&%.       &&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&,..     &&&&&&&&&&&&&&&     #%&&&&&&&&&&&&@        &&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&.       &&&&&&&&&&&@&&@@&&@@@@@@&&&&&&&&&&@        &&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&&@*  ,&&&&&&&&&&&                 (%&&&&&&&#.    ./&&&&&&&&&&&&&&
        &&&&&&&&&&&&&&**********#@&&&&%*                 .&&&&&&%**********#@&&&&&&&&&&&
        &&&&&&&&&&&.               @&&%*                  &&&&.               @&&&&&&&&&
        &&&&&&&&&&&&@@@@@@@@@@@@@@&&&&&&@@@@@@@@@@@@@@@@@&&&&&&@@@@@@@@@@@@@@&@&&&&&&&&&
        &&&&&&&&%%%%%%%%%%%%%%%%%%&%%&%%%%%%%%%%%%%%%%%%&%%%%%%%%%%%%%%%%%%%%%%%%&&&&&&&
        &&&&&&&&&&&&&&&&&&(      /&&@/   ,&&&&&&&&&&&&.  .&&&/   #&&&&&&*   /%&&&&&&&&&&
        &&&&&&&&&&&&&&(  ,@%%@* *&&&&&     &&&&&&&&&     @&&&#   @&&&&&%*   @&&&&&&&&&&&
        &&&&&&&&&&&&&(  .%&&&&&&&&&&&&      .&&&&&#  #   &&&&%   &&&&&&%/   @&&&&&&&&&&&
        &&&&&&&&&&&&&   *%&&&&&&&&&&&#  &&    &&%* .%@   &&&&%              &&&&&&&&&&&&
        &&&&&&&&&&&&&    &&&&&&&&&&&%*  &&&    /  #%&&   @&&&#   &&&&&&%*   @&&&&&&&&&&&
        &&&&&&&&&&&&&&    &%&&%&% @&&   &&&&/    &&&&#   @&&%/   @&&&&&%,   @&&&&&&&&&&&
        &&&&&&&&&&&&&&&*      .%%&&&/  (&&&&&&  &&&&&*   .@&&   ,&&&&&&&   ,#&&&&&&&&&&&
        &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
        &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&""")
    print(ascii_art)
    print()
    print(
        "Welcome to the CMH Playset Preserver for Crusader Kings 3"
        "\nGitHub repository: https://github.com/Ant0nidas/CMH-Playset-Preserver"
        "\nJoin CMH on Discord: https://discord.gg/GuDjt9YQ"
        "\nPlease answer the prompts to continue:"
    )


def locate_ck3_directory():
    current_path = pathlib.Path(__file__).resolve()

    # Try parent directories successively
    for path in current_path.parents:
        # Ensure mod directory exists
        # (Also guards against being located under steamapps/common)
        if path.name == "Crusader Kings III" and (path / "mod").is_dir():
            return path

    return None


def open_db_connection(ck3_directory):
    # Connect to the launcher's SQLite database
    database = str(ck3_directory / "launcher-v2.sqlite")
    db_connection = sqlite3.connect(database)
    # Make query results have dict-like interface
    db_connection.row_factory = sqlite3.Row
    return db_connection


def select_playset(ck3_directory):
    db_connection = open_db_connection(ck3_directory)

    # List playsets in the order the launcher uses.
    # Playset names aren't required to be unique,
    # so their internal IDs are needed.
    sql = "SELECT id, name FROM playsets ORDER BY rowid;"
    playsets = db_connection.execute(sql).fetchall()
    db_connection.close()

    if len(playsets) == 0:
        print("No playsets found in the launcher.")
        return None

    for i, playset in enumerate(playsets):
        print(f"{i + 1}. {playset['name']}")
    print()
    choice = int(input("Select the playset by typing the corresponding number: ")) - 1

    return playsets[choice]


def get_playset_mods(ck3_directory, playset_id):
    db_connection = open_db_connection(ck3_directory)

    sql = (
        "SELECT m.displayName, m.dirPath, m.status, pm.enabled"
        " FROM mods AS m"
        " JOIN playsets_mods AS pm ON m.id = pm.modId"
        " WHERE pm.playsetId = ?"
        " ORDER BY pm.position;"
    )
    mods = db_connection.execute(sql, (playset_id,)).fetchall()
    db_connection.close()

    return mods


def get_valid_filename(name):
    # Remove/replace characters unsafe for filenames the way Django does it
    s = str(name).strip().replace(" ", "_")
    s = re.sub(r"[^-\w.]", "", s)
    if s in {"", ".", ".."}:
        # For pathological cases, fall back to base64
        return base64.urlsafe_b64encode(name)
    return s


def get_new_mod_name(playset_name):
    # Default name appends current local date to original playset name.
    # E.g. "My Playset (2024-05-06)"
    date = datetime.date.today().isoformat()
    # .mod files can't handle backslashes in names, except for \"
    cleaned_name = playset_name.replace("\\", "")
    new_mod_name = f"{cleaned_name} ({date})"

    while True:
        new_mod_name_input = input(f"Enter preserved playset name [{new_mod_name}]: ")
        if "\\" not in new_mod_name_input:
            break
        print("ERROR: Name cannot contain \\")
    new_mod_name = new_mod_name_input or new_mod_name

    return new_mod_name


def copy_mod_folders(mods, new_mod_folder, pbar=None):
    # Many Windows systems will error on paths > 260 characters
    MAX_PATH = 260
    # Create a progress bar if one was not provided
    pbar = pbar or tqdm(total=len(mods))
    try:
        # Iterate through mods as a queue in the correct order
        while mods:
            # Copy the content of the mod folder into the destination
            pbar.write(f"Copying {mods[0]['displayName']}")
            shutil.copytree(
                mods[0]["dirPath"],
                str(new_mod_folder),
                ignore=shutil.ignore_patterns(".git"),
                dirs_exist_ok=True,
            )
            pbar.update()
            # Remove mod from front of queue when successful
            del mods[0]
    except shutil.Error as e:
        # Error's first argument is a list of (src, dst, error_msg) tuples
        # (simultaneous errors are common)
        _, first_error_dst, first_error_msg = e.args[0][0]
        if (
            len(first_error_dst) > MAX_PATH
            and "No such file or directory" in first_error_msg
        ):
            # Stop progress bar from overwriting the following exchange
            pbar.close()
            print()
            shorter_path_input = input(
                'ERROR: I/O error matching "path too long" Windows scenario.'
                f"\nCurrent mod folder name is {new_mod_folder.name}."
                "\nEnter a new shorter folder name to retry,"
                "\nor press Enter to print the error and exit: "
            )
            if not shorter_path_input:
                raise
            # Preserve progress by renaming the existing folder
            new_mod_folder = new_mod_folder.rename(
                new_mod_folder.parent / shorter_path_input
            )
            print()
            # Recreate progress bar
            new_pbar = tqdm(total=pbar.total, initial=pbar.n)
            # Try again to copy the remaining mods to the new destination
            new_mod_folder = copy_mod_folders(mods, new_mod_folder, new_pbar)
        else:
            raise

    pbar.close()

    # Propagate correct mod folder upwards
    return new_mod_folder


def clean_combined_folder(destination_path):
    for item in destination_path.iterdir():
        if item.is_file():
            item.unlink()
    print("Finished cleaning up.")


def create_descriptor_file(destination_path, mod_name, game_version):
    escaped_name = mod_name.replace('"', '\\"')
    descriptor_content = dedent(f"""\
        version="1.0"
        tags={{
            "Utilities"
        }}
        name="{escaped_name}"
        supported_version="{game_version}.*"
        """)
    descriptor_path = destination_path / "descriptor.mod"
    with descriptor_path.open("w", encoding="utf-8") as descriptor_file:
        descriptor_file.write(descriptor_content)


def create_mod_file(mod_directory, mod_folder_name, mod_name, game_version):
    escaped_name = mod_name.replace('"', '\\"')
    mod_file_content = dedent(f"""\
        version="1.0"
        tags={{
            "Utilities"
        }}
        name="{escaped_name}"
        supported_version="{game_version}.*"
        path="mod/{mod_folder_name}"
        """)
    mod_file_path = mod_directory / f"{mod_folder_name}.mod"
    with mod_file_path.open("w", encoding="utf-8") as mod_file:
        mod_file.write(mod_file_content)


def create_playset(ck3_directory, mod_name, mod_folder_name):
    mod_id = str(uuid.uuid4())  # new random ID
    mod_file = f"mod/{mod_folder_name}.mod"
    created = time.time_ns() // 1000000  # Unix time in milliseconds
    playset_id = str(uuid.uuid4())  # new random ID
    playset_name = mod_name

    db_connection = open_db_connection(ck3_directory)
    db_connection.execute(
        "INSERT INTO mods (id, gameRegistryId, displayName, status, source, createdDate) VALUES"
        " (?, ?, ?, 'ready_to_play', 'local', ?);",
        (mod_id, mod_file, mod_name, created),
    )
    db_connection.execute(
        "INSERT INTO playsets (id, name, isActive, loadOrder, createdOn, syncState) VALUES"
        " (?, ?, 0, 'custom', ?, 'NOT_ELIGIBLE');",
        (playset_id, playset_name, created),
    )
    db_connection.execute(
        "INSERT INTO playsets_mods (playsetId, modId, position) VALUES (?, ?, 0);",
        (playset_id, mod_id),
    )
    # Commit the changes in one transaction
    db_connection.commit()
    db_connection.close()


def main():
    display_welcome_message()

    # Agreement prompt
    print()
    agreement = input(
        "By using this method, you agree to not seek advice for gameplay or mod-related issues,"
        "\nbe it on the authors discord servers, steam pages, or elsewhere."
        "\nNo support or troubleshooting can be given."
        "\nHave you understood? - y/n: "
    )
    if agreement.lower() != "y":
        print()
        print("Exiting program. Please re-run the script if you agree to the terms.")
        return

    ck3_directory = locate_ck3_directory()

    if ck3_directory is None:
        print("Game directory not found. Ensure the script is in the correct location.")
        return

    mod_directory = ck3_directory / "mod"

    # Select the playset based on the launcher database
    print()
    playset = select_playset(ck3_directory)
    if playset is None:
        return

    # Prompt for the game version
    game_version = input(
        "Enter the game version this collection will be created for (e.g., 1.12): "
    )

    # Load the mods from the selected playset
    mods = get_playset_mods(ck3_directory, playset["id"])

    # Mods that are missing on disk (red error sign in launcher)
    # have a different status from ready_to_play.
    if not_found_mods := [m for m in mods if m["status"] != "ready_to_play"]:
        print()
        print("ERROR: The following mods cannot be found:")
        for mod in not_found_mods:
            mods.remove(mod)
            print(f"- {mod['displayName']}")
        continue_input = input("Ignore these mods and continue? - y/[n]: ")
        if continue_input.lower() != "y":
            print("Exiting program.")
            return

    # Skip mods disabled in playset and inform user
    if disabled_mods := [m for m in mods if not m["enabled"]]:
        print()
        print(
            "The following mods are disabled in the selected playset"
            "\nand will NOT be included in the preserved playset:"
        )
        for mod in disabled_mods:
            mods.remove(mod)
            print(f"- {mod['displayName']}")

    # Prompt user for mod & playset name
    new_mod_name = get_new_mod_name(playset["name"])

    new_mod_folder_name = get_valid_filename(new_mod_name)
    new_mod_folder = mod_directory / new_mod_folder_name

    # Copy mod folders based on the launcher database
    # (Mod folder may change to recover from long path errors)
    print()
    new_mod_folder = copy_mod_folders(mods, new_mod_folder)

    # Clean up the combined folder
    clean_combined_folder(new_mod_folder)

    # Create the descriptor.mod file
    create_descriptor_file(new_mod_folder, new_mod_name, game_version)

    # Create the .mod file in the root directory
    create_mod_file(mod_directory, new_mod_folder.name, new_mod_name, game_version)

    print()
    print(f"Mod {new_mod_name} created in {new_mod_folder}")

    # Prompt to create the playset in the launcher's DB
    print()
    create_playset_input = input("Create new playset in launcher? - [y]/n: ")
    if create_playset_input.lower() != "n":
        create_playset(ck3_directory, new_mod_name, new_mod_folder.name)
        print(f"Playset {new_mod_name} created in launcher")


if __name__ == "__main__":
    main()
    print()
    input("Press Enter to exit...")
