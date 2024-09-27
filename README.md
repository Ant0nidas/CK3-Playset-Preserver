# Crusader Kings 3 Playset Preserver

This program reads a playset from the CK3 launcher, retrieves its mods, and copies all of them into one new local mod which will be safe from unwanted updates.

## Who?

| Role            | GitHub                                   | Discord   | Paradox Forum                                                                          |
| --------------- | ---------------------------------------- | --------- | -------------------------------------------------------------------------------------- |
| Developer       | [escalonn](https://github.com/escalonn)  | @taio.ii  | [IoannesBarbarus](https://forum.paradoxplaza.com/forum/members/ioannesbarbarus.951663) |
| Release Manager | [Kaepbora](https://github.com/Ant0nidas) | @kaepbora | [Sir Antou](https://forum.paradoxplaza.com/forum/members/sir-antou.601346)             |

## Why?

The problem we face with each official CK3 patch is asynchronous mod updates. This results in an issue where some mods are updated, while others are not. Since Steam does not have the option to download older versions of mods, players are left with incomplete or broken playsets. It can take months before all mods in a large playset are updated.

## How?

A "snapshot" of a current playset of your choice is created, which is stored locally without further updates. This way, it will be possible to continue existing campaign or play older versions of CK3 until your favorite mods are updated. The load order of the playset is used to decide which files will appear in the snapshot, and which will not (because they should be overridden according to the playset's definition).

## Installation

Download [the latest release](https://github.com/Ant0nidas/CK3-Playset-Preserver/releases/latest), and unzip the downloaded archive into your mod folder, so that `CK3_PP.exe` is at a location like `mod/CK3-Playset-Preserver-vX.Y.Z/CK3_PP.exe`.

| OS       | Default location of mod folder                                       |
| -------- | -------------------------------------------------------------------- |
| Windows  | `%USERPROFILE%\Documents\Paradox Interactive\Crusader Kings III\mod` |
| macOS    | `~/Documents/Paradox Interactive/Crusader Kings III/mod`             |
| Linux    | `~/.local/share/Paradox Interactive/Crusader Kings III/mod`          |

To update Crusader Kings 3 Playset Preserver, delete the unzipped folder, and then install the new version.

Alternatively, clone the repository in your mod folder.

## Usage

1. Ensure that your chosen playset is defined correctly in the CK3 launcher, and that you have enough disk space to accommodate the copying of all its mods.

2. On Windows, run `CK3_PP.exe`.

    Or, on any platform, ensure your environment satisfies `requirements.txt`, and run `CK3_PP.py` with Python 3.

    Or, on any platform, install [Pixi](https://pixi.sh), and run `pixi run start_py`.

3. Follow the prompts until the program exits.

4. Once the process is done, the preserved playset mod will appear in the launcher after restarting it.

## Notes

- **You are not allowed to distribute the preserved playset.** All contents belong to their respective authors and you have to get their consents.

- **No support or troubleshooting is provided for preserved playsets.** By using this method, you agree not to seek advice for gameplay or mod-related issues on the authors' Discord servers, Steam pages, or elsewhere.

- The program has been developed and tested on Windows only. MacOS and Linux support is "best effort."

- All types of mods are supported: Steam Workshop, local, and Paradox Mods.

- It isn't necessary to have the launcher open while the program runs.

- The created mod will have a README documenting all source mods and their versions, and another file indicating which source mod provided each file (inspired by CK2's HIP).

- The program will never overwrite an existing mod.

- For additional help, troubleshooting, or feature suggestions, visit [the CMH Discord](https://discord.gg/GuDjt9YQ).
