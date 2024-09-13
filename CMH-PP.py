import datetime
import json
import os
import pathlib
import re
import shutil
import sqlite3
from textwrap import dedent
import time
import uuid

import semver
from tqdm import tqdm


def display_welcome_message():
    ascii_art = dedent("""\
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
        &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&""")
    print(ascii_art)
    print()
    print(
        "Welcome to the Crusader Kings 3 Playset Preserver - A project by Community Mods for Historicity"
        "\nGitHub repository: https://github.com/Ant0nidas/CMH-Playset-Preserver"
        "\nCMH Discord: https://discord.gg/GuDjt9YQ"
        "\n"
        "\nThis installer will read a chosen playset from your launcher and create a merged local copy of it."
        "\n"
        "\nPlease respond to the following prompts by typing your answer and pressing Enter."
        "\nIf a prompt has a default answer, it will appear [in brackets]."
        "\nSimply press Enter with an empty response to accept the default answer."
        "\nTo exit the program at any time, press Ctrl+C."
    )
    input("Press Enter to continue... ")


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


def get_game_version(mods):
    # Decide a useful version default:
    # Find the highest version required by any mod.
    # Provide an arbitrary default if no mods have a suitable requiredVersion
    version = max(
        filter(semver.Version.is_valid, (mod["requiredVersion"] for mod in mods)),
        key=semver.Version.parse,
        default="1.12.*",
    )

    # Prompt user
    while True:
        version_input = input(
            f"Enter the game version this collection will be created for [{version}]: "
        ).strip()
        if not version_input:
            break
        elif not semver.Version.is_valid(version_input):
            # semver might be too permissive, but it should be fine
            print("ERROR: Version format must be MAJOR.MINOR.PATCH (* is allowed)")
        else:
            version = version_input
            break

    return version


def get_playset_mods(ck3_directory, playset_id):
    db_connection = open_db_connection(ck3_directory)

    sql = (
        "SELECT m.gameRegistryId, m.displayName, m.tags, m.requiredVersion, m.dirPath, m.status, pm.enabled"
        " FROM mods AS m"
        " JOIN playsets_mods AS pm ON m.id = pm.modId"
        " WHERE pm.playsetId = ?"
        " ORDER BY pm.position;"
    )
    mods = db_connection.execute(sql, (playset_id,)).fetchall()
    db_connection.close()

    return mods


def get_new_mod_name(playset_name):
    # Default name appends current local date to original playset name.
    # E.g. "My Playset (2024-05-06)"
    date = datetime.date.today().isoformat()
    # Remove tabs and backslashes
    cleaned_name = re.sub(r"\t\\", "", playset_name)
    new_mod_name = f"{cleaned_name} ({date})"

    while True:
        new_mod_name_input = input(
            f"Enter preserved playset name [{new_mod_name}]: "
        ).strip()
        if not new_mod_name_input:
            break
        elif "\\" in new_mod_name_input:
            print("ERROR: Name cannot contain \\")
        elif "\t" in new_mod_name_input:
            print("ERROR: Name cannot contain tab character")
        elif len(new_mod_name_input) < 3:
            print("ERROR: Name must be at least 3 characters long")
        else:
            new_mod_name = new_mod_name_input
            break

    return new_mod_name


def copy_mod_folders(mods, new_mod_folder, pbar=None):
    def handle_dir(src, names):
        # Called for every directory to be copied
        pbar.update()
        return [".git"] if ".git" in names else []  # Ignore .git

    # Many Windows systems will error on paths >= 260 characters
    MAX_PATH = 260
    # If there isn't already a progress bar,
    # this is the first function call, not a recursive one
    if not pbar:
        # Make a copy of the mod list to modify, leaving the original unchanged
        mods = list(mods)
        # Count the total number of directories to be copied,
        # and make that the basis for the progress bar
        dir_count = 0
        for mod in mods:
            dir_count += 1  # Count the top-level directory too
            for _, dirs, _ in os.walk(mod["dirPath"]):
                # Don't count .git because it and its contents won't be copied
                if ".git" in dirs:
                    dirs.remove(".git")
                dir_count += len(dirs)
        # Create the progress bar.
        # cmd.exe often doesn't handle Unicode well, so everyone has to use ASCII
        # (It would be nice to detect cmd.exe and special-case it)
        pbar = tqdm(total=dir_count, ascii=True, unit="")
    try:
        # Iterate through mods as a queue in the correct order
        while mods:
            # Keep track of the position the progress bar should revert to
            # in case of retrying after an error
            pbar_checkpoint = pbar.n
            # Copy the content of the mod folder into the destination.
            # The "ignore" function is called for every directory to be copied,
            # so it will handle both ignoring .git and updating the progress bar
            pbar.write(f"Copying {mods[0]['displayName']}")
            shutil.copytree(
                mods[0]["dirPath"],
                new_mod_folder,
                ignore=handle_dir,
                dirs_exist_ok=True,
            )
            # Remove mod from front of queue when successful
            del mods[0]
    except shutil.Error as e:
        # Error's first argument is a list of (src, dst, error_msg) tuples
        # (simultaneous errors are common)
        _, first_error_dst, first_error_msg = e.args[0][0]
        if (
            len(first_error_dst) >= MAX_PATH
            and "No such file or directory" in first_error_msg
        ):
            max_length = max(len(dst) for _, dst, _ in e.args[0])
            shorter_by = max_length - MAX_PATH + 1
            # Stop progress bar from overwriting the following exchange
            pbar.close()

            print()
            print(
                'ERROR: I/O error matching Windows "file path too long" scenario.'
                f"\nCurrent mod folder name is {new_mod_folder.name},"
                f"\ncausing a path to reach {max_length} characters long."
            )
            while True:
                new_path_input = input(
                    f"\nEnter a new folder name at least {shorter_by} characters shorter to recover and continue,"
                    "\nor press Enter to print the error and exit: "
                ).strip()
                if not new_path_input:
                    raise
                elif "\t" in new_path_input:
                    print("ERROR: Folder name cannot contain tab character")
                elif matches := re.findall(r'[*"./:<>?\\|]', new_path_input):
                    print(f'ERROR: Folder name cannot contain {"".join(matches)}')
                else:
                    break
            # Preserve progress by renaming the existing folder
            new_mod_folder = new_mod_folder.rename(
                new_mod_folder.parent / new_path_input
            )
            print()
            # Recreate progress bar
            new_pbar = tqdm(
                total=pbar.total, ascii=True, unit="", initial=pbar_checkpoint
            )
            # Try again to copy the remaining mods to the new destination
            new_mod_folder = copy_mod_folders(mods, new_mod_folder, new_pbar)
        else:
            # Don't attempt to handle any other errors
            raise

    pbar.close()

    # Propagate correct mod folder upwards
    return new_mod_folder


def clean_combined_folder(destination_path):
    # A mess of thumbnails and READMEs wind up at the top of the mod folder.
    # Remove all of them
    for item in destination_path.iterdir():
        if item.is_file():
            item.unlink()


def create_dotmod_files(new_mod_folder, new_mod_name, game_version, mods):
    # Gather mod tags from already-fetched data
    # and replace_path lines from their .mod files
    tags = set()
    replace_paths = set()
    for mod in mods:
        # The tags column from the DB is JSON. There should never be
        # quotation marks inside the tags, but escape them just in case.
        tags.update(tag.replace('"', '\\"') for tag in json.loads(mod["tags"]))
        src_mod_file_path = new_mod_folder.parent.parent / mod["gameRegistryId"]
        with src_mod_file_path.open(encoding="utf-8") as file:
            # Read .mod file with excessive tolerance
            for line in file:
                regex = r'\s*replace_path\s*=\s*"([^"]*(?:\\"[^"]*)*)"\s*(?:#.*)?'
                if match := re.fullmatch(regex, line):
                    replace_paths.add(match[1])

    escaped_name = new_mod_name.replace('"', '\\"')
    lines = [
        'version="1.0.0"',
        "tags={",
        *(f'\t"{tag}"' for tag in sorted(tags)),
        "}",
        f'name="{escaped_name}"',
        f'supported_version="{game_version}"',
        path_line := f'path="mod/{new_mod_folder.name}"',
        *(f'replace_path="{path}"' for path in sorted(replace_paths)),
    ]

    # UTF-8 encoding, LF line endings
    mod_file_path = new_mod_folder.parent / f"{new_mod_folder.name}.mod"
    with mod_file_path.open("w", encoding="utf-8", newline="") as file:
        file.writelines(x + "\n" for x in lines)

    # descriptor.mod normally lacks the path line
    lines.remove(path_line)

    descriptor_path = new_mod_folder / "descriptor.mod"
    with descriptor_path.open("w", encoding="utf-8", newline="") as file:
        file.writelines(x + "\n" for x in lines)


def create_playset(ck3_directory, mod_name, mod_folder_name):
    mod_id = str(uuid.uuid4())  # New random ID
    mod_file = f"mod/{mod_folder_name}.mod"
    created = time.time_ns() // 1000000  # Unix time in milliseconds
    playset_id = str(uuid.uuid4())  # New random ID
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
        "No support or troubleshooting is provided for preserved playsets."
        "\nBy using this method, you agree to not seek advice for gameplay or mod-related issues,"
        "\nbe it on the authors' Discord servers, Steam pages, or elsewhere."
        "\nYou are not allowed to distribute the preserved playset. All content belong to their respective authors."
        "\nHave you understood? - y/[n]: "
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

    # Prompt for the game version
    game_version = get_game_version(mods)

    # Prompt user for mod & playset name
    new_mod_name = get_new_mod_name(playset["name"])

    # Remove/replace characters disallowed in filename
    new_mod_folder_name = re.sub(r'[*"./:<>?|]', "", new_mod_name)
    new_mod_folder = mod_directory / new_mod_folder_name

    # Copy mod folders based on the launcher database
    # (Mod folder may change to recover from long path errors)
    print()
    new_mod_folder = copy_mod_folders(mods, new_mod_folder)

    # Clean up the combined folder
    clean_combined_folder(new_mod_folder)

    # Create the <name>.mod and descriptor.mod files
    create_dotmod_files(new_mod_folder, new_mod_name, game_version, mods)

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
