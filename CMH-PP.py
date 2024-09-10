import base64
import datetime
import pathlib
import re
import shutil
import sqlite3
from textwrap import dedent
import time
import uuid


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
        "\n"
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


def copy_mod_folders(mods, destination_path):
    not_found_mods = []

    # Prompt to skip if some mods in playset aren't enabled
    if not all(mod["enabled"] for mod in mods):
        skip_disabled = input(
            "Selected playset contains disabled mods. Skip disabled mods in preserved playset? - [y]/n: "
        )
        if skip_disabled.lower() != "n":
            mods = [mod for mod in mods if mod["enabled"]]

    for mod in mods:
        # Mods that are missing on disk (red error sign in launcher)
        # have a different status from ready_to_play.
        if mod["status"] == "ready_to_play":
            # Copy the content of the mod folder directly into the destination
            shutil.copytree(
                mod["dirPath"],
                str(destination_path),
                ignore=shutil.ignore_patterns(".git"),
                dirs_exist_ok=True,
            )
            print(f"Copied contents of {mod["displayName"]}")
        else:
            print(f"{mod['displayName']} not found.")
            not_found_mods.append(mod["displayName"])

    return not_found_mods


def clean_combined_folder(destination_path):
    for item in destination_path.iterdir():
        if item.is_file():
            item.unlink()
    print("Finished cleaning up.")


def create_descriptor_file(destination_path, mod_name, game_version):
    descriptor_content = dedent(f"""\
        version="1.0"
        tags={{
            "Utilities"
        }}
        name="{mod_name}"
        supported_version="{game_version}.*"
        """)
    descriptor_path = destination_path / "descriptor.mod"
    with descriptor_path.open("w", encoding="utf-8") as descriptor_file:
        descriptor_file.write(descriptor_content)
    print(f"Created descriptor.mod file in {destination_path}")


def create_mod_file(mod_directory, mod_folder_name, mod_name, game_version):
    mod_file_content = dedent(f"""\
        version="1.0"
        tags={{
            "Utilities"
        }}
        name="{mod_name}"
        supported_version="{game_version}.*"
        path="mod/{mod_folder_name}"
        """)
    mod_file_path = mod_directory / f"{mod_folder_name}.mod"
    with mod_file_path.open("w", encoding="utf-8") as mod_file:
        mod_file.write(mod_file_content)
    print(f"Created {mod_folder_name}.mod file in {mod_directory}")


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
    agreement = input(
        "By using this method, you agree to not seek advice for gameplay or mod-related issues,"
        "\nbe it on the authors discord servers, steam pages, or elsewhere."
        "\nNo support or troubleshooting can be given."
        "\nHave you understood? - y/n: "
    )
    if agreement.lower() != "y":
        print("Exiting program. Please re-run the script if you agree to the terms.")
        return

    ck3_directory = locate_ck3_directory()

    if ck3_directory is None:
        print("Game directory not found. Ensure the script is in the correct location.")
        return

    mod_directory = ck3_directory / "mod"

    # Select the playset based on the launcher database
    playset = select_playset(ck3_directory)
    if playset is None:
        return

    # Prompt for the game version
    game_version = input(
        "Enter the game version this collection will be created for (e.g., 1.12): "
    )

    # Load the mods from the selected playset
    mods = get_playset_mods(ck3_directory, playset["id"])

    # Prompt user for mod & playset name.
    # Default name appends current local date to original playset name.
    # E.g. "My Playset (2024-05-06)"
    date = datetime.date.today().isoformat()
    new_mod_name = f"{playset['name']} ({date})"
    new_mod_name_input = input(f"Enter preserved playset name [{new_mod_name}]: ")
    new_mod_name = new_mod_name_input or new_mod_name

    # Create a new folder with the name of the selected playlist
    new_mod_folder_name = get_valid_filename(new_mod_name)
    new_mod_folder = mod_directory / new_mod_folder_name
    new_mod_folder.mkdir(exist_ok=True)
    print(f"Created new mod folder at {new_mod_folder}")

    # Copy mod folders based on the launcher database
    not_found_mods = copy_mod_folders(mods, new_mod_folder)

    # Clean up the combined folder
    clean_combined_folder(new_mod_folder)

    # Create the descriptor.mod file
    create_descriptor_file(new_mod_folder, new_mod_name, game_version)

    # Create the .mod file in the root directory
    create_mod_file(mod_directory, new_mod_folder_name, new_mod_name, game_version)

    print()

    # Summary of missing mods
    if not_found_mods:
        print("The following mods could not be copied:")
        for mod_name in not_found_mods:
            print(f"- {mod_name}")
    else:
        print("All mods were copied successfully")

    print()

    should_create_playset = input(
        "Create playset in launcher?"
        "\nWARNING: this operation will modify the launcher-v2.sqlite file containing your playsets."
        "\nBack up this file or risk launcher data corruption. - y/[n]: "
    )
    if should_create_playset.lower() == "y":
        create_playset(ck3_directory, new_mod_name, new_mod_folder_name)
        print("Preserved playset created successfully")


if __name__ == "__main__":
    main()
    input("Press Enter to exit...")
