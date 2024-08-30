import os
import shutil
import json

def display_welcome_message():
    ascii_art = """&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
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
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&"""
    print(ascii_art)
    print("\nWelcome to the CMH Playset Preserver for Crusader Kings 3\nGitHub repository: https://github.com/Ant0nidas/CMH-Playset-Preserver\nJoin CMH on Discord: https://discord.gg/GuDjt9YQ\nPlease answer the prompts to continue:\n")

def get_mods_from_json(json_path):
    with open(json_path, 'r') as file:
        data = json.load(file)
    return data['mods']

def copy_mod_folders(steam_path, mods, destination_path):
    workshop_path = os.path.join(steam_path, 'steamapps', 'workshop', 'content', '1158310')
    
    if not os.path.exists(workshop_path):
        print(f"Workshop folder not found at {workshop_path}. Check the Steam directory.")
        return

    not_found_mods = []

    for mod in mods:
        mod_folder = os.path.join(workshop_path, mod['steamId'])
        if os.path.exists(mod_folder):
            # Copy the content of the mod folder directly into the destination
            for item in os.listdir(mod_folder):
                s = os.path.join(mod_folder, item)
                d = os.path.join(destination_path, item)
                if os.path.isdir(s):
                    if '.git' in s:  # Skip .git directories
                        continue
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            print(f"Copied contents of {mod['displayName']}")
        else:
            print(f"{mod['displayName']} with Steam ID {mod['steamId']} not found.")
            not_found_mods.append(mod['displayName'])

    return not_found_mods

def clean_combined_folder(destination_path):
    for item in os.listdir(destination_path):
        item_path = os.path.join(destination_path, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
    print("Finished cleaning up.")

def create_descriptor_file(destination_path, mod_name, game_version):
    descriptor_content = f'''version="1.0"
tags={{
    "Utilities"
}}
name="{mod_name}"
supported_version="{game_version}.*"
'''
    descriptor_path = os.path.join(destination_path, "descriptor.mod")
    with open(descriptor_path, 'w') as descriptor_file:
        descriptor_file.write(descriptor_content)
    print(f"Created descriptor.mod file in {destination_path}")

def create_mod_file(mod_directory, mod_name, game_version, new_mod_folder):
    mod_file_content = f'''version="1.0"
tags={{
    "Utilities"
}}
name="{mod_name}"
supported_version="{game_version}.*"
path="{new_mod_folder.replace(os.sep, '/')}"
'''
    mod_file_path = os.path.join(mod_directory, f"{mod_name}.mod")
    with open(mod_file_path, 'w') as mod_file:
        mod_file.write(mod_file_content)
    print(f"Created {mod_name}.mod file in {mod_directory}")

def select_json_file(mod_directory):
    json_files = [f for f in os.listdir(mod_directory) if f.endswith('.json')]
    if len(json_files) == 0:
        print("No .json files found in the directory.")
        return None
    elif len(json_files) == 1:
        return json_files[0]
    else:
        print("Multiple .json files found:")
        for i, file in enumerate(json_files):
            print(f"{i + 1}. {file}")
        choice = int(input("Select the .json file by typing the corresponding number: ")) - 1
        return json_files[choice]

def main():
    display_welcome_message()

    # Agreement prompt
    agreement = input(
        "By using this method, you agree to not seek advice for gameplay or mod-related issues,\nbe it on the authors discord servers, steam pages, or elsewhere.\nNo support or troubleshooting can be given.\n"
        "Have you understood? - y/n: "
    )
    if agreement.lower() != 'y':
        print("Exiting program. Please re-run the script if you agree to the terms.")
        return

    # The parent directory of the script (one level up from the script's directory)
    mod_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    
    # Ensure the mod directory exists
    if not os.path.exists(mod_directory):
        print(f"Mod directory not found at {mod_directory}. Ensure the script is in the correct location.")
        return
    
    # Select the .json file
    json_file_name = select_json_file(mod_directory)
    if json_file_name is None:
        return
    json_file_path = os.path.join(mod_directory, json_file_name)
    
    # Prompt for the game version
    game_version = input("Enter the game version this collection will be created for (e.g., 1.12): ")

    # Load the mods from the selected .json file
    mods = get_mods_from_json(json_file_path)

    # Prompt user for the Steam installation directory
    steam_path = input("Enter the directory of your Steam installation (e.g., C:\\Program Files (x86)\\Steam): ")

    # Create a new folder with the name of the selected .json file (without the extension)
    new_mod_folder_name = os.path.splitext(json_file_name)[0]
    new_mod_folder = os.path.join(mod_directory, new_mod_folder_name)
    os.makedirs(new_mod_folder, exist_ok=True)
    print(f"Created new mod folder at {new_mod_folder}")

    # Copy mod folders based on the JSON data
    not_found_mods = copy_mod_folders(steam_path, mods, new_mod_folder)

    # Clean up the combined folder
    clean_combined_folder(new_mod_folder)

    # Create the descriptor.mod file
    create_descriptor_file(new_mod_folder, new_mod_folder_name, game_version)

    # Create the .mod file in the root directory
    create_mod_file(mod_directory, new_mod_folder_name, game_version, new_mod_folder)

    # Summary of missing mods
    if not_found_mods:
        print("\nThe following mods were not found:")
        for mod_name in not_found_mods:
            print(f"- {mod_name}")
    else:
        print("\nAll mods were copied successfully!")

if __name__ == "__main__":
    main()
    input("Press Enter to exit...")
