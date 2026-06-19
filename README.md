# joy2midi

A small Windows-friendly Python app for turning a gamepad into MIDI CC controls with a guided learn mode.

By **Audi Etoffe and Acid Reign Productions**  
https://acidreignproductions.com

DJ Audi Etoffe:  
https://linktr.ee/etoffe

This app is **100% free under the GNU GPL v2 license**.  
Support development / buy me a coffee:  
https://buymeacoffee.com/acidrp

## v0.3.1 features

- Automatically opens the selected MIDI output on startup
- Automatically reopens the MIDI output when selecting/changing a profile
- Shows clear MIDI connection status in the main window
- Sends MIDI by default without needing to press **Open Port** first
- Double-clicking the tray icon restores the main window when minimized to tray
- Loads the previous profile automatically on startup
- Saves the last-used profile path when loading/saving
- Optional **Start with Windows**
- Optional **Minimize to tray**
- Optional **Start hidden in tray**
- Tray menu with **Show joy2midi** and **Exit**
- Uses the Acid Reign purple/blue image as the generated app/window/EXE icon
- Keeps explicit RtMidi backend packaging for the Windows EXE

## What it does

joy2midi lets you quickly convert a gamepad/controller into MIDI CC controls:

1. Pick your controller.
2. Pick a MIDI output such as a loopMIDI port.
3. Click **Start Learn**.
4. Press or move a control.
5. joy2midi assigns the next available MIDI CC automatically.
6. Save the profile.

## Features

- Clean Tkinter GUI
- Controller selector
- MIDI output selector
- Works with loopMIDI ports on Windows
- Guided learn mode
- Auto-assigns MIDI CC numbers
- Saves and loads JSON profiles
- Editable mapping table
- Supports buttons, analog axes/sticks/triggers, and D-pad/hat controls
- Button modes: momentary or toggle
- Axis options: deadzone, invert, min/max value

## Easiest Windows build

Install **Python 3.12 64-bit** from python.org. During install, check **Add Python to PATH**.

Then double-click:

```bat
build_exe.bat
```

The build script will:

1. Look specifically for Python 3.12, then 3.11, then 3.10
2. Create a clean local `.venv` virtual environment
3. Upgrade `pip`, `setuptools`, and `wheel`
4. Install dependencies using prebuilt wheels only
5. Generate `app_icon.png` and `app_icon.ico` from the embedded logo
6. Run PyInstaller with the app icon and RtMidi backend included
7. Create `dist\joy2midi.exe`

## Run without compiling

```bat
run_app.bat
```

## Windows MIDI setup

Windows does not include a simple built-in virtual MIDI cable.

Install **loopMIDI**, create a virtual port, then open joy2midi and select that port under **MIDI Output**.

Then in Traktor, Ableton, Resolume, or another MIDI-capable app, select the same loopMIDI port as a MIDI input.

## Manual EXE build

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install --only-binary=:all: -r requirements.txt
python make_icon.py
python -m PyInstaller --clean --noconfirm --onefile --windowed --name joy2midi --icon=app_icon.ico --add-data "app_icon.ico;." --add-data "app_icon.png;." --runtime-hook=pyinstaller_runtime_hook.py --hidden-import=mido.backends.rtmidi --hidden-import=rtmidi --hidden-import=pystray._win32 --collect-submodules=mido.backends --collect-submodules=rtmidi --collect-submodules=pystray --collect-binaries=rtmidi joy2midi.py
```

## If pygame fails to install

If you see `failed to build pygame when getting requirements`, pip is probably trying to compile pygame from source.

Fixes:

1. Install **Python 3.12 64-bit** from python.org.
2. Delete the `.venv` folder inside the joy2midi folder.
3. Run `build_exe.bat` again.

The build script uses `--only-binary=:all:` so it fails early instead of trying to compile pygame.

## How joystick axes and triggers are handled

Gamepads usually expose analog sticks and linear triggers as joystick **axes**.

The app reads the raw axis value from pygame, usually in this range:

```text
-1.0 to +1.0
```

Then it converts that to MIDI CC:

```text
-1.0 -> CC value 0
 0.0 -> CC value 64
+1.0 -> CC value 127
```

Some controllers expose triggers differently:

```text
unpressed trigger -> -1.0, pressed trigger -> +1.0
```

Others expose triggers like this:

```text
unpressed trigger -> 0.0, pressed trigger -> +1.0
```

joy2midi does not assume a specific controller layout. When you move a trigger during Learn Mode, it maps that trigger as an axis and sends it as a continuous MIDI CC.

## Deadzone

There is a visible **Default Axis/Trigger Deadzone** field on the main screen.

That value is used when learning new analog controls.

You can also double-click an individual axis/trigger mapping and set a custom deadzone for that specific control.

Suggested values:

```text
Analog sticks: 0.08 to 0.15
Linear triggers: 0.00 to 0.05
```

If a stick sends MIDI while sitting untouched, increase the deadzone. If a trigger feels unresponsive near the start of its travel, lower the deadzone.

## License

joy2midi is free software released under the GNU GPL v2 license.
