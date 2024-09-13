# Crusader Kings 3 Playset Preserver

This program reads a playset from the CK3 launcher, retrieves its mods, and copies all of them into one new single local mod which will not receive any updates.

## Why?

The problem we face with each official CK3 patch is asynchronous mod updates. This results in an issue where some mods are updated, while others are not. Since Steam does not have the option to download older versions of mods, players are left with incomplete or broken playsets. It can take months before all mods in a large playset are updated.

## How?

A "snapshot" of a current playset of your choice is created, which is stored locally without further updates. This way, it will be possible to continue existing campaign or play older versions of CK3 until your favorite mods are updated. The load order of the playset is used to decide which files will appear in the snapshot, and which will not (because they should be overridden according to the playset's definition).

## Installation

Click "Code," choose "Download ZIP," and unzip the downloaded archive into your mod folder, so that `CK3_PP.exe` is at a location like `mod/CK3-Playset-Preserver-main/CK3_PP.exe`.

| OS       | Default location                                                     |
| -------- | -------------------------------------------------------------------- |
| Windows  | `%USERPROFILE%\Documents\Paradox Interactive\Crusader Kings III\mod` |
| macOS    | `~/Documents/Paradox Interactive/Crusader Kings III/mod`             |
| Linux    | `~/.local/share/Paradox Interactive/Crusader Kings III/mod`          |

To update Crusader Kings 3 Playset Preserver, delete the unzipped folder, and then install the new version.

Alternatively, clone the repository in your mod folder.

## Usage

1. Ensure that your chosen playset is defined correctly in the CK3 launcher, and that you have enough disk space to accommodate the copying of all its mods.

2. On Windows, run `CK3_PP.exe`.

    On macOS and Linux, ensure your environment satisfies `requirements.txt` and run `CK3_PP.py` with Python (>=3.8).

3. Follow the prompts until the program exits.

4. Once the process is done, the preserved playset mod will appear in the launcher after restarting it.

## Notes

- All types of mods are handled: Steam Workshop, local, and Paradox Mods.

- It isn't necessary to have the launcher open while the program runs.

- No support or troubleshooting is provided for preserved playsets. By using this method, you agree not to seek advice for gameplay or mod-related issues on the authors' Discord servers, Steam pages, or elsewhere.

- You are not allowed to distribute the preserved playset. All content belong to their respective authors and you have to get their consents.

- The installer has been developed and tested on Windows. It may not work correctly on MacOS and Linux.

- For additional help, troubleshooting, or feature suggestions, visit the CMH Discord: https://discord.gg/GuDjt9YQ
