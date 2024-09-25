from datetime import date
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from textwrap import dedent
import time
import traceback
import uuid

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
        "\nGitHub repository: https://github.com/Ant0nidas/CK3-Playset-Preserver"
        "\nCMH Discord: https://discord.gg/GuDjt9YQ"
        "\n"
        "\nThis program will read a chosen playset from your launcher and create a merged local copy of it."
        "\n"
        "\nPlease respond to the following prompts by typing your answer and pressing Enter."
        "\nIf a prompt has a default answer, it will appear [in brackets]."
        "\nSimply press Enter with an empty response to accept the default answer."
        "\nTo exit the program at any time, press Ctrl+C."
    )
    input("Press Enter to continue... ")


def locate_ck3_directory():
    current_path = Path(__file__).resolve()

    # Try parent directories successively
    for path in current_path.parents:
        # Ensure mod directory exists
        # (Also guards against being located under steamapps/common)
        if path.name == "Crusader Kings III" and (path / "mod").is_dir():
            return path

    return None


def locate_database(ck3_directory):
    # The release version of the launcher and the beta version use two different
    # files. Either or both might be present. If both are present, the correct
    # one should be the most recently modified one.
    release_db = ck3_directory / "launcher-v2.sqlite"
    beta_db = ck3_directory / "launcher-v2_openbeta.sqlite"

    release_db_exists = release_db.exists()
    beta_db_exists = beta_db.exists()

    if release_db_exists and not beta_db_exists:
        return release_db
    if not release_db_exists and beta_db_exists:
        return beta_db
    print()
    if not release_db_exists and not beta_db_exists:
        # fall back to the most recently modified sqlite file
        # (e.g. paradox changes to launcher-v3.sqlite)
        fallback = max(
            ck3_directory.glob("*.sqlite"),
            key=lambda p: p.stat().st_mtime_ns,
            default=None,
        )
        if not fallback:
            return None
        print("WARNING: expected launcher database not found.")
        print(f"Attempting to proceed with {fallback.name}.")
        return fallback

    release_db_stat = release_db.stat()
    beta_db_stat = beta_db.stat()

    print("Multiple launcher databases detected.")
    if beta_db_stat.st_mtime_ns > release_db_stat.st_mtime_ns:
        print("Using beta launcher database (most recently modified).")
        return beta_db
    else:
        print("Using release launcher database (most recently modified).")
        return release_db


def open_db_connection(db_path):
    # Connect to the launcher's SQLite database
    db_connection = sqlite3.connect(db_path)
    # Make query results have dict-like interface
    db_connection.row_factory = sqlite3.Row
    return db_connection


def select_playset(db_path):
    db_connection = open_db_connection(db_path)

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
    def sort_key(version):
        # CK3 version matching rules:
        # * matches 0 or more characters (including .)
        # a spec like 1.* will match version 1
        tokens = re.findall(r"\w+|[^\w*]+|\*", version)
        # Sort numeric after non-numeric (edge case)
        tokens = [
            (True, int(t)) if re.fullmatch(r"\d+", t, re.A) else (False, t)
            for t in tokens
        ]
        dotstar = [(False, "."), (False, "*")]
        tokens_min = tokens[:-2] if tokens[-2:] == dotstar else tokens
        # Compare first by minimum version described by the range
        min_key = [t for t in tokens_min if t[1] != "*"]
        # Compare second by maximum version described by the range
        max_key = [(t[1] == "*", *t) for t in tokens]
        return min_key, max_key

    # Decide a useful version default:
    # Find the highest version required by any mod.
    # Provide an arbitrary default if somehow no mods have a suitable requiredVersion
    mod_versions = (mod["requiredVersion"] for mod in mods)
    version = max(mod_versions, key=sort_key, default="1.12.*")

    # Prompt user
    while True:
        version_input = input(
            f"Enter the game version this playset is for (* is allowed) [{version}]: "
        ).strip()
        if not version_input:
            break
        elif "\\" in version_input:
            print("ERROR: Game version cannot contain \\")
        elif "\t" in version_input:
            print("ERROR: Game version cannot contain tab character")
        else:
            version = version_input
            break

    return version


def get_playset_mods(db_path, playset_id):
    db_connection = open_db_connection(db_path)

    sql = (
        "SELECT m.gameRegistryId, m.displayName, m.version, m.tags,"
        " m.requiredVersion, m.dirPath, m.archivePath, m.status, pm.enabled"
        " FROM mods AS m"
        " JOIN playsets_mods AS pm ON m.id = pm.modId"
        " WHERE pm.playsetId = ?"
        " ORDER BY pm.position;"
    )
    mods = db_connection.execute(sql, (playset_id,)).fetchall()
    db_connection.close()

    return mods


def get_new_mod_name(playset_name, mod_directory):
    # Default name appends current local date to original playset name.
    # E.g. "My Playset (2024-05-06)"
    # Remove tabs and backslashes
    cleaned_name = re.sub(r"\t\\", "", playset_name)
    default_mod_name = f"{cleaned_name} ({date.today()})"

    while True:
        new_mod_name = input(
            f"Enter preserved playset name [{default_mod_name}]: "
        ).strip()
        if "\\" in new_mod_name:
            print("ERROR: Name cannot contain \\")
        elif "\t" in new_mod_name:
            print("ERROR: Name cannot contain tab character")
        elif 1 <= len(new_mod_name) < 3:
            print("ERROR: Name must be at least 3 characters long")
        else:
            new_mod_name = new_mod_name or default_mod_name
            # Remove/replace characters disallowed in filename
            folder_name = re.sub(r'[*"/:<>?|]', "", new_mod_name).rstrip(".")
            new_mod_folder = mod_directory / folder_name
            dotmod = new_mod_folder.with_name(f"{new_mod_folder.name}.mod")
            if new_mod_folder.exists():
                print(f'ERROR: "{new_mod_folder.name}" already exists.')
            elif dotmod.exists():
                print(f'ERROR: "{dotmod.name}" already exists.')
            else:
                break

    return new_mod_name, new_mod_folder


def copy_mod_folders(mods, new_mod_folder):
    def copy_mod_folders_with_retry(new_mod_folder, pbar):
        def handle_dir(src, names):
            # Called for every directory to be copied
            pbar.update()
            return [".git"] if ".git" in names else []  # Ignore .git

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
                if archive_path := mods[0]["archivePath"]:
                    mod_path = archive_dirs[archive_path].name
                else:
                    mod_path = mods[0]["dirPath"]
                shutil.copytree(
                    mod_path,
                    new_mod_folder,
                    ignore=handle_dir,
                    dirs_exist_ok=True,
                )
                if archive_path:
                    # Clean up temporary directory of archive contents
                    archive_dirs[archive_path].cleanup()
                    del archive_dirs[archive_path]
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
                    f'\nCurrent mod folder name is "{new_mod_folder.name}",'
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
                    elif new_path_input.endswith("."):
                        print("ERROR: Folder name cannot end with .")
                    elif matches := re.findall(r'[*"/:<>?\\|]', new_path_input):
                        print(f"ERROR: Folder name cannot contain {''.join(matches)}")
                    else:
                        replacement_folder = new_mod_folder.parent / new_path_input
                        if replacement_folder.exists():
                            print(f'ERROR: "{new_path_input}" already exists.')
                        else:
                            break
                # Preserve progress by renaming the existing folder
                new_mod_folder = new_mod_folder.rename(replacement_folder)
                print()
                # Recreate progress bar
                new_pbar = tqdm(
                    total=pbar.total, initial=pbar_checkpoint, **tqdm_kwargs
                )
                # Try again to copy the remaining mods to the new destination
                new_mod_folder = copy_mod_folders_with_retry(new_mod_folder, new_pbar)
            else:
                # Don't attempt to handle any other errors
                raise

        pbar.close()
        # Propagate folder upwards, in case it changed
        return new_mod_folder

    # Many Windows systems will error on paths >= 260 characters
    MAX_PATH = 260

    # cmd.exe often doesn't handle Unicode well, so everyone has to use ASCII
    # (It would be nice to detect cmd.exe and special-case it)
    tqdm_kwargs = {"ascii": True, "unit": "dirs"}

    # This dict is used to generate file_to_mod_map.txt later
    file_to_mod_map = {}

    # Make a copy of the mod list to modify, leaving the original unchanged
    mods = list(mods)

    # Create the directory
    new_mod_folder.mkdir()

    archive_dirs = {}
    # Count the total number of directories to be copied,
    # and make that the basis for the progress bar
    dir_count = 0
    try:
        for mod in mods:
            dir_count += 1  # Count the top-level directory too
            if mod["archivePath"]:
                # Paradox Mods
                # The archive is extracted to a temporary directory before being
                # copied like the others to simplify processing. This does waste
                # a little time and space.
                td = tempfile.TemporaryDirectory()
                shutil.unpack_archive(mod["archivePath"], td.name)
                archive_dirs[mod["archivePath"]] = td
                mod_path = td.name
            else:
                # Steam Workshop and local mods
                mod_path = mod["dirPath"]
            for root, dirs, files in os.walk(mod_path):
                rel_root = Path(root).relative_to(mod_path)
                if rel_root != Path("."):  # top-level files are removed
                    for file in files:
                        file_to_mod_map[rel_root / file] = mod["displayName"]
                # Don't count .git because it and its contents won't be copied
                if ".git" in dirs:
                    dirs.remove(".git")
                dir_count += len(dirs)
        # Create the progress bar
        pbar = tqdm(total=dir_count, **tqdm_kwargs)
        new_mod_folder = copy_mod_folders_with_retry(new_mod_folder, pbar)
    finally:
        if archive_dirs:
            for td in archive_dirs.values():
                td.cleanup()

    # Propagate correct mod folder upwards
    return new_mod_folder, file_to_mod_map


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
    escaped_game_version = game_version.replace('"', '\\"')
    lines = [
        'version="1.0.0"',
        "tags={",
        *(f'\t"{tag}"' for tag in sorted(tags)),
        "}",
        f'name="{escaped_name}"',
        f'supported_version="{escaped_game_version}"',
        path_line := f'path="mod/{new_mod_folder.name}"',
        *(f'replace_path="{path}"' for path in sorted(replace_paths)),
    ]

    # UTF-8 encoding, LF line endings
    mod_file_path = new_mod_folder.with_name(f"{new_mod_folder.name}.mod")
    with mod_file_path.open("w", encoding="utf-8", newline="") as file:
        file.writelines(x + "\n" for x in lines)

    # descriptor.mod normally lacks the path line
    lines.remove(path_line)

    descriptor_path = new_mod_folder / "descriptor.mod"
    with descriptor_path.open("w", encoding="utf-8", newline="") as file:
        file.writelines(x + "\n" for x in lines)


def create_mod_version_files(new_mod_folder, playset, mods, file_to_mod_map):
    with (new_mod_folder / "README.txt").open("w", encoding="utf-8") as f:
        print(
            "This mod was generated using Crusader Kings 3 Playset Preserver."
            "\nGitHub repository: https://github.com/Ant0nidas/CK3-Playset-Preserver"
            "\nCMH Discord: https://discord.gg/GuDjt9YQ",
            file=f,
        )
        print(file=f)
        print(f"Source playset: {playset['name']}", file=f)
        print(f"Date: {date.today()}", file=f)
        print("Contents:", file=f)
        for mod in mods:
            print(f"{mod['displayName']} ({mod['version']})", file=f)

    with (new_mod_folder / "file_to_mod_map.txt").open("w", encoding="utf-8") as f:
        for file, mod in sorted(file_to_mod_map.items()):
            print(f"{file} <- [{mod}]", file=f)


def create_playset(db_path, mod_name, mod_folder_name):
    mod_id = str(uuid.uuid4())  # New random ID
    mod_file = f"mod/{mod_folder_name}.mod"
    created = time.time_ns() // 1000000  # Unix time in milliseconds
    playset_id = str(uuid.uuid4())  # New random ID
    playset_name = mod_name

    db_connection = open_db_connection(db_path)
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
        print("Exiting program. Please re-run the program if you agree to the terms.")
        return

    ck3_directory = locate_ck3_directory()
    if ck3_directory is None:
        print()
        print(
            "ERROR: Game directory not found. Ensure the program is in the correct location."
        )
        return

    mod_directory = ck3_directory / "mod"

    db_path = locate_database(ck3_directory)
    if db_path is None:
        print("ERROR: Launcher database not found.")
        return

    # Select the playset based on the launcher database
    print()
    playset = select_playset(db_path)
    if playset is None:
        return

    # Load the mods from the selected playset
    mods = get_playset_mods(db_path, playset["id"])

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
    print()
    game_version = get_game_version(mods)

    # Prompt user for mod/playset name
    new_mod_name, new_mod_folder = get_new_mod_name(playset["name"], mod_directory)

    # Copy mod folders based on the launcher database
    # (Mod folder may change to recover from long path errors)
    print()
    print("Starting copy operation...")
    new_mod_folder, file_to_mod_map = copy_mod_folders(mods, new_mod_folder)

    # Clean up the combined folder
    clean_combined_folder(new_mod_folder)

    # Create the <name>.mod and descriptor.mod files
    create_dotmod_files(new_mod_folder, new_mod_name, game_version, mods)

    create_mod_version_files(new_mod_folder, playset, mods, file_to_mod_map)

    print()
    print(f"Preserved playset mod {new_mod_name} created in {new_mod_folder}")

    # Prompt to create the playset in the launcher's DB
    print()
    create_playset_input = input(
        "Create a new playset in launcher containing only this new mod? - [y]/n: "
    )
    if create_playset_input.lower() != "n":
        create_playset(db_path, new_mod_name, new_mod_folder.name)
        print(f"Playset {new_mod_name} created in launcher")

    print()
    print("If launcher is open, close and reopen it to see changes.")


if __name__ == "__main__":
    try:
        main()
    except:  # noqa: E722
        # Intercept all exceptions so user can see them before the window exits
        traceback.print_exc()
        print()
    finally:
        input("Press Enter to exit...")
