# FTL: Co-Op Mode Alpha

Two-player online co-op for **FTL: Faster Than Light**. Each captain flies their own ship in their own copy of the game, and the two of you travel, vote on events and fight the same enemy together.

> **This is a very early alpha, shared so more people can find bugs.**
> Expect things to break. The furthest it has been played so far is sector 3. Please do not expect to finish a run yet, and please report what goes wrong.

Current version: **v0.28.16** (not yet played by anyone other than the two original testers).

## What works today

- Two captains, two different vanilla ships, separate crews, scrap and inventories.
- A shared map: both click the same beacon to jump.
- Shared events: both click an option to vote; matching votes are applied on both games.
- Shared enemy: both ships shoot the same enemy, and its hull, shields and systems are the same for both captains. Each captain is attacked separately.
- Coordinated pause: Space pauses for both, and both must be ready to resume.
- A live view of your partner's ship above your own.

## What does not work yet

- **Vanilla FTL only.** Multiverse and other overhaul mods are not supported.
- **Windows only**, FTL 1.6.9 with Hyperspace 1.20.0.
- **Every run uses the same map seed.** A host-chosen seed is planned.
- **Many enemies are fought separately.** If the enemy has cloaking, a clone bay, mind control, or crew or boarding drones, each captain fights their own copy at that beacon. Shared combat returns at the next beacon.
- **Shared enemies never surrender or flee.**
- **Your own teleporter, hacking and mind control are not shared.** If your ship has one of these installed, every fight is separate. Pick starting ships without them and do not buy them.
- **The flagship is untested.**
- No save and continue, no reconnect in the middle of a run.
- Known visual glitch: the second player's shots can look like misses when they hit. Damage is correct.
- Your partner's drones are not drawn on your screen, only their shots.

See `SUPPORT_MATRIX.txt` for the detailed equipment list.

## What this mod does to your computer

Please read this before installing.

- It **replaces `Hyperspace.dll`** in your FTL folder with a modified build of Hyperspace 1.20.0. Your existing DLL is backed up next to it first.
- A small Python program, the **companion**, must run next to the game on both PCs.
  - On the host it listens on **TCP port 38473** for the other player.
  - On both PCs it listens on `127.0.0.1:38474` for the local game only.
  - It reads the game's `FTL_HS.log`.
  - It **sends key presses to the FTL window** (F13, F14, F15 and number keys) to apply agreed event choices. It only does this while FTL is the foreground window.
- It writes two log files into the `companion` folder: `bridge_debug.txt` and `fleet_diagnostics.txt`.

Some antivirus tools dislike programs that send key presses or replace DLLs. All source code is in this repository.

## Requirements

Both players need:

1. **FTL: Faster Than Light** on Windows, at version **1.6.9**.
2. **Hyperspace 1.20.0**, installed and working by itself first. Follow the Hyperspace install guide: https://ftl-hyperspace.github.io/FTL-Hyperspace/
3. **Slipstream Mod Manager** (used to install Hyperspace).
4. **Python 3.10 or newer** from https://www.python.org/ with the default options (the `py` launcher and Tk).
5. **A network path to the host.** The simplest is a virtual LAN tool such as Hamachi, ZeroTier or Tailscale that both of you join. Port forwarding TCP 38473 on the host's router also works.
6. **The same version of this mod.** Mismatched versions are refused.

## Install (both players)

1. Close FTL and Slipstream.
2. Download the mod: use the zip on the [Releases page](https://github.com/Antrisa/FTL-CoOp-Mode-Alpha/releases) if there is one, or [download this repository as a zip](https://github.com/Antrisa/FTL-CoOp-Mode-Alpha/archive/refs/heads/main.zip). Extract it to a new folder and keep the folders inside it together.
3. In Slipstream, add `companion\FleetCoop_Ingame_Panel_v0.28.16.ftl` to your mods, tick it **below Hyperspace**, and click Patch. Leave Hyperspace ticked. Do not tick any other gameplay mods.
4. Close Slipstream.

When you update to a newer version, untick the old `FleetCoop_Ingame_Panel` file first.

## Start a session

Do these in order, on both PCs.

1. Run `companion\Start_Fleet_Link.bat`.
2. In the companion window:
   - One player chooses **Host**, the other chooses **Join**.
   - Enter a captain name.
   - **Both** players enter the **host's** IP address (the host's address on your virtual LAN, or the host's public address if port forwarding).
   - Check the `FTL_HS.log` path. It is in your FTL game folder; use Browse if the guess is wrong.
   - Click **Connect fleet**. Both names should appear under Connected Captains.
3. Tick **Enable game link** in the companion on both PCs.
4. Run `companion\Start_FTL_Coop.bat` and select your `FTLGame.exe` when asked. This backs up your current `Hyperspace.dll`, installs this mod's DLL and starts FTL.
5. In FTL, press **F8**. It should show both captains and both game links. Close the panel.
6. Both start a **new game**. Choose vanilla ships without a teleporter, hacking or mind control.
7. Leave the companion running the whole time.

## Controls

| Key | What it does |
|---|---|
| Click an event option | Vote. When both votes match, the choice is applied on both games. A tie picks one of the two votes at random. |
| Click a beacon on the map | Vote to jump there. Both must pick the same beacon. |
| Space | Pause, or mark yourself ready. Both captains must be ready to resume. |
| F6 | With an event screen open: split this beacon so each captain plays it alone until the next jump. Use this if one of you has a screen the other does not. |
| F7 | Inspect your partner's ship (pauses). |
| F8 | Co-op status panel. |
| F9 | Change the layout of the two-ship view. |
| F10 | Crisp or smooth scaling for the ship view. |

Keep FTL as the active window while an event choice is being applied.

## If something goes wrong

- **"SEPARATE FIGHT" banner:** expected for unsupported enemies. Fight your own copy, then jump together.
- **An event screen only one of you can see:** press F6 with it open.
- **Companion shows "game mod unconfirmed":** that player is on a different `.ftl` version or did not patch.
- **Connection refused with a protocol message:** the two companions are different versions.
- **Game will not start after installing:** check that plain Hyperspace 1.20.0 works first.

## Reporting bugs

Please open an [issue](https://github.com/Antrisa/FTL-CoOp-Mode-Alpha/issues) in this repository, or message the author on Discord, and attach, from **both** players:

- `FTL_HS.log` from the FTL game folder
- `bridge_debug.txt` and `fleet_diagnostics.txt` from the `companion` folder

Say what you were doing and roughly when it happened.

**Privacy note:** these logs contain your Windows user name in file paths, your captain names and the IP address you connected to. Look through them, or remove those lines, before posting publicly.

## Uninstall

1. In Slipstream, untick `FleetCoop_Ingame_Panel` and click Patch.
2. In your FTL folder, delete `Hyperspace.dll` and rename the newest `Hyperspace.before-v0…dll.bak` file back to `Hyperspace.dll`. Reinstalling Hyperspace 1.20.0 does the same thing.

## For developers

- `companion/` Python companion and relay, Lua game scripts, tests, built `.ftl` (`build_mod.py` rebuilds it)
- `native/` C++ additions to Hyperspace and the upstream patch
- `native_bin/` built custom `Hyperspace.dll`
- `docs/ARCHITECTURE.md` how the pieces fit together
- `docs/changelog/` release notes
- `tools/` a Lua 5.3 syntax checker and mock-test runner

The in-game panels and the companion still use the working title "Fleet Co-op".

## Credits and licence

This is an unofficial fan project. It is not affiliated with Subset Games or the Hyperspace team, and it contains no FTL game files.

It is built on [FTL: Hyperspace](https://github.com/FTL-Hyperspace/FTL-Hyperspace) 1.20.0 by the Hyperspace contributors, and is shared under the same Creative Commons Attribution-ShareAlike 4.0 licence. See `ATTRIBUTION.md`, `LICENSE.md` and the `licenses/` folder.

Most of the code was written with AI assistance (ChatGPT and Claude) and tested by two players.
