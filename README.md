# joy2midi

A small Windows-friendly Python app for turning a gamepad into MIDI CC controls with a guided learn mode.

By **Audi Etoffe and Acid Reign Productions**  
https://acidreignproductions.com

DJ Audi Etoffe:  
https://linktr.ee/etoffe

This app is **100% free under the GNU GPL v2 license**.  
Support development / buy me a coffee:  
https://buymeacoffee.com/acidrp

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

Install Python 3.10 or newer from python.org. During install, check **Add Python to PATH**.

Then double-click:

```bat
build_exe.bat
```

The build script will:

1. Create a local `.venv` virtual environment
2. Upgrade `pip`, `setuptools`, and `wheel`
3. Install all dependencies
4. Run PyInstaller
5. Create `dist\joy2midi.exe`

This is the recommended option for Windows computers because it avoids most missing `setuptools` / `wheel` / PyInstaller setup problems.

## Install for development

```bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## Windows MIDI setup

Windows does not include a simple built-in virtual MIDI cable.

Install **loopMIDI**, create a virtual port, then open joy2midi and select that port under **MIDI Output**.

Then in Traktor, Ableton, Resolume, or another MIDI-capable app, select the same loopMIDI port as a MIDI input.

## Run without compiling

```bat
python joy2midi.py
```

Or double-click:

```bat
run_app.bat
```

## Manual EXE build

```bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m PyInstaller --clean --noconfirm --onefile --windowed --name joy2midi joy2midi.py
```

The `.exe` will appear in the `dist` folder.

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

## Suggested Traktor defaults

- Buttons: momentary CC 127 on press, CC 0 on release
- D-pad: four momentary buttons
- Triggers: absolute CC 0-127
- Sticks: absolute CC 0-127 with a deadzone around 0.08 to 0.15
- Use a controller button as a shift modifier inside Traktor if you want multiple layers

## License

joy2midi is free software released under the GNU GPL v2 license.
