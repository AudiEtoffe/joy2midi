#!/usr/bin/env python3
"""joy2midi - guided gamepad to MIDI CC mapper."""
from __future__ import annotations

import json
import os
import sys
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import pygame
except Exception as exc:
    pygame = None
    PYGAME_ERROR = exc
else:
    PYGAME_ERROR = None

try:
    import mido
    import mido.backends.rtmidi  # explicit import for PyInstaller
    mido.set_backend("mido.backends.rtmidi")
except Exception as exc:
    mido = None
    MIDO_ERROR = exc
else:
    MIDO_ERROR = None

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None

APP_NAME = "joy2midi"
APP_VERSION = "0.3.1"
APPDATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "joy2midi"
SETTINGS_PATH = APPDATA_DIR / "settings.json"
PROFILE_DIR = Path(__file__).resolve().parent / "profiles"
PROFILE_DIR.mkdir(exist_ok=True)

DEFAULT_SETTINGS = {
    "last_profile": "",
    "midi_output_name": "",
    "start_with_windows": False,
    "minimize_to_tray": False,
    "start_minimized_to_tray": False,
}

DEFAULT_PROFILE = {
    "app": APP_NAME,
    "version": APP_VERSION,
    "device_name": "",
    "device_guid": "",
    "midi_output_name": "",
    "midi_channel": 0,
    "next_cc": 20,
    "axis_deadzone": 0.08,
    "axis_send_threshold": 1,
    "mappings": {},
}


def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent / name


def load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@dataclass
class Mapping:
    key: str
    kind: str
    label: str
    cc: int
    channel: int = 0
    mode: str = "momentary"
    invert: bool = False
    deadzone: float = 0.08
    min_value: int = 0
    max_value: int = 127
    enabled: bool = True


class MidiOut:
    def __init__(self):
        self.port = None
        self.name = ""

    def is_open(self) -> bool:
        return self.port is not None

    def outputs(self) -> list[str]:
        if mido is None:
            return []
        try:
            return mido.get_output_names()
        except Exception as exc:
            print("MIDI output scan failed:", exc)
            return []

    def open(self, name: str) -> None:
        self.close()
        if not name:
            raise RuntimeError("No MIDI output selected.")
        if mido is None:
            raise RuntimeError(f"mido import failed: {MIDO_ERROR}")
        self.port = mido.open_output(name)
        self.name = name

    def close(self) -> None:
        if self.port:
            try:
                self.port.close()
            except Exception:
                pass
        self.port = None
        self.name = ""

    def cc(self, control: int, value: int, channel: int) -> None:
        if not self.port:
            return
        self.port.send(mido.Message(
            "control_change",
            control=max(0, min(127, int(control))),
            value=max(0, min(127, int(value))),
            channel=max(0, min(15, int(channel))),
        ))


class Gamepads:
    def __init__(self):
        self.ready = False
        self.joys = []

    def start(self) -> None:
        if pygame is None:
            raise RuntimeError(f"pygame import failed: {PYGAME_ERROR}")
        if not self.ready:
            pygame.init()
            pygame.joystick.init()
            self.ready = True
        self.refresh()

    def refresh(self):
        self.joys = []
        if pygame is None:
            return []
        pygame.joystick.quit()
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            self.joys.append(joy)
        return self.joys

    def names(self) -> list[str]:
        return [f"{i}: {j.get_name()}" for i, j in enumerate(self.joys)]

    def get(self, index: int):
        return self.joys[index] if 0 <= index < len(self.joys) else None

    def stop(self) -> None:
        if pygame and self.ready:
            pygame.quit()
        self.ready = False


class Profile:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULT_PROFILE))

    def new(self):
        self.data = json.loads(json.dumps(DEFAULT_PROFILE))

    def load(self, path: Path):
        self.data = load_json(path, DEFAULT_PROFILE)
        self.normalize()

    def save(self, path: Path):
        self.normalize()
        save_json(path, self.data)

    def normalize(self):
        for key, value in DEFAULT_PROFILE.items():
            self.data.setdefault(key, value)
        self.data.setdefault("mappings", {})

    def mappings(self) -> dict[str, Mapping]:
        out = {}
        for key, raw in self.data.get("mappings", {}).items():
            raw = dict(raw)
            raw.setdefault("key", key)
            try:
                out[key] = Mapping(**raw)
            except TypeError:
                out[key] = Mapping(key=key, kind=raw.get("kind", "button"), label=raw.get("label", key), cc=int(raw.get("cc", 20)))
        return out

    def set(self, mapping: Mapping):
        self.data["mappings"][mapping.key] = asdict(mapping)

    def delete(self, key: str):
        self.data.get("mappings", {}).pop(key, None)

    def next_cc(self) -> int:
        used = {m.cc for m in self.mappings().values()}
        cc = int(self.data.get("next_cc", 20))
        while cc in used and cc <= 127:
            cc += 1
        if cc > 127:
            cc = 0
            while cc in used and cc <= 127:
                cc += 1
        return max(0, min(127, cc))

    def bump_cc(self, cc: int):
        self.data["next_cc"] = max(int(self.data.get("next_cc", 20)), int(cc) + 1)


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def set_start_with_windows(enabled: bool) -> None:
    if os.name != "nt":
        return
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


class MappingEditor(tk.Toplevel):
    def __init__(self, parent, mapping: Mapping):
        super().__init__(parent)
        self.title(f"Edit {mapping.label}")
        self.resizable(False, False)
        self.result: Optional[Mapping] = None
        self.mapping = mapping
        self.transient(parent)
        self.grab_set()

        self.label = tk.StringVar(value=mapping.label)
        self.cc = tk.IntVar(value=mapping.cc)
        self.channel = tk.IntVar(value=mapping.channel + 1)
        self.mode = tk.StringVar(value=mapping.mode)
        self.invert = tk.BooleanVar(value=mapping.invert)
        self.deadzone = tk.DoubleVar(value=mapping.deadzone)
        self.min_value = tk.IntVar(value=mapping.min_value)
        self.max_value = tk.IntVar(value=mapping.max_value)
        self.enabled = tk.BooleanVar(value=mapping.enabled)

        f = ttk.Frame(self, padding=14)
        f.grid(sticky="nsew")
        row = 0
        for text, widget in [
            ("Label", ttk.Entry(f, textvariable=self.label, width=32)),
            ("MIDI CC", ttk.Spinbox(f, from_=0, to=127, textvariable=self.cc, width=8)),
            ("MIDI Channel", ttk.Spinbox(f, from_=1, to=16, textvariable=self.channel, width=8)),
        ]:
            ttk.Label(f, text=text).grid(row=row, column=0, sticky="w", pady=4)
            widget.grid(row=row, column=1, sticky="w", pady=4)
            row += 1

        ttk.Label(f, text="Mode").grid(row=row, column=0, sticky="w", pady=4)
        modes = ["absolute"] if mapping.kind == "axis" else ["momentary", "toggle"]
        ttk.Combobox(f, values=modes, textvariable=self.mode, state="readonly", width=14).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(f, text="Value range").grid(row=row, column=0, sticky="w", pady=4)
        r = ttk.Frame(f)
        r.grid(row=row, column=1, sticky="w", pady=4)
        ttk.Spinbox(r, from_=0, to=127, textvariable=self.min_value, width=6).grid(row=0, column=0)
        ttk.Label(r, text=" to ").grid(row=0, column=1)
        ttk.Spinbox(r, from_=0, to=127, textvariable=self.max_value, width=6).grid(row=0, column=2)
        row += 1

        if mapping.kind == "axis":
            ttk.Checkbutton(f, text="Invert axis", variable=self.invert).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
            row += 1
            ttk.Label(f, text="Deadzone").grid(row=row, column=0, sticky="w", pady=4)
            ttk.Spinbox(f, from_=0.0, to=0.95, increment=0.01, textvariable=self.deadzone, width=8).grid(row=row, column=1, sticky="w", pady=4)
            row += 1

        ttk.Checkbutton(f, text="Enabled", variable=self.enabled).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1
        ttk.Label(f, text=f"Internal key: {mapping.key}").grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
        row += 1
        b = ttk.Frame(f)
        b.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(b, text="Save", command=self.save).grid(row=0, column=1)

    def save(self):
        try:
            self.result = Mapping(
                key=self.mapping.key,
                kind=self.mapping.kind,
                label=self.label.get().strip() or self.mapping.label,
                cc=max(0, min(127, int(self.cc.get()))),
                channel=max(0, min(15, int(self.channel.get()) - 1)),
                mode=self.mode.get(),
                invert=self.invert.get(),
                deadzone=max(0.0, min(0.95, float(self.deadzone.get()))),
                min_value=max(0, min(127, int(self.min_value.get()))),
                max_value=max(0, min(127, int(self.max_value.get()))),
                enabled=self.enabled.get(),
            )
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Invalid mapping", str(exc))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1120x740")
        self.minsize(980, 640)
        self.try_set_icon()

        self.settings = load_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        self.midi = MidiOut()
        self.gamepads = Gamepads()
        self.profile = Profile()
        self.profile_path: Optional[Path] = None

        self.controller_index = tk.IntVar(value=0)
        self.output_name = tk.StringVar(value=self.settings.get("midi_output_name", ""))
        self.learning = tk.BooleanVar(value=False)
        self.continuous = tk.BooleanVar(value=True)
        self.deadzone = tk.DoubleVar(value=0.08)
        self.status = tk.StringVar(value="Ready")
        self.learn_text = tk.StringVar(value="Click Start Learn, then press or move a gamepad control.")
        self.start_with_windows = tk.BooleanVar(value=bool(self.settings.get("start_with_windows")))
        self.minimize_to_tray = tk.BooleanVar(value=bool(self.settings.get("minimize_to_tray")))
        self.start_minimized_to_tray = tk.BooleanVar(value=bool(self.settings.get("start_minimized_to_tray")))
        self.axis_last: dict[str, int] = {}
        self.toggle_state: dict[str, bool] = {}
        self.hat_previous: dict[int, tuple[int, int]] = {}
        self.tray_icon = None
        self.exiting = False

        self.build_ui()
        self.start_backends()
        self.refresh_all()
        self.load_last_profile()
        self.after(250, self.auto_open_midi)
        self.protocol("WM_DELETE_WINDOW", self.close_or_tray)
        self.bind("<Unmap>", self.on_unmap)
        self.after(8, self.poll)
        if self.start_minimized_to_tray.get() and self.minimize_to_tray.get():
            self.after(300, self.hide_to_tray)

    def try_set_icon(self):
        png = resource_path("app_icon.png")
        ico = resource_path("app_icon.ico")
        try:
            if png.exists():
                self._icon_img = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._icon_img)
            elif ico.exists() and os.name == "nt":
                self.iconbitmap(str(ico))
        except Exception:
            pass

    def save_settings(self):
        self.settings.update({
            "last_profile": str(self.profile_path or ""),
            "midi_output_name": self.output_name.get(),
            "start_with_windows": self.start_with_windows.get(),
            "minimize_to_tray": self.minimize_to_tray.get(),
            "start_minimized_to_tray": self.start_minimized_to_tray.get(),
        })
        save_json(SETTINGS_PATH, self.settings)

    def link(self, parent, text: str, url: str, row: int, col: int):
        label = ttk.Label(parent, text=text, cursor="hand2", foreground="#0645AD")
        label.grid(row=row, column=col, sticky="e", pady=(2, 0))
        label.bind("<Button-1>", lambda _e: webbrowser.open(url))

    def build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        header = ttk.Frame(self, padding=(14, 12))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)
        ttk.Label(header, text=APP_NAME, font=("Segoe UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="guided gamepad-to-MIDI CC mapper").grid(row=1, column=0, sticky="w")
        credits = ttk.Frame(header)
        credits.grid(row=0, column=2, rowspan=3, sticky="e")
        ttk.Label(credits, text="by ").grid(row=0, column=0, sticky="e")
        self.link(credits, "Audi Etoffe and Acid Reign Productions", "https://acidreignproductions.com", 0, 1)
        self.link(credits, "DJ Audi Etoffe: linktr.ee/etoffe", "https://linktr.ee/etoffe", 1, 1)
        self.link(credits, "100% free under the GNU GPL v2 license • Buy me a coffee", "https://buymeacoffee.com/acidrp", 2, 1)

        top = ttk.LabelFrame(self, text="Device, MIDI Output, and Startup", padding=12)
        top.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        top.columnconfigure(1, weight=1)
        top.columnconfigure(4, weight=1)
        ttk.Label(top, text="Controller").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.controller_box = ttk.Combobox(top, state="readonly", width=38)
        self.controller_box.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.controller_box.bind("<<ComboboxSelected>>", self.controller_selected)
        ttk.Button(top, text="Rescan Controllers", command=self.refresh_controllers).grid(row=0, column=2, padx=(0, 16))
        ttk.Label(top, text="MIDI Output").grid(row=0, column=3, sticky="w", padx=(0, 8))
        self.output_box = ttk.Combobox(top, state="readonly", textvariable=self.output_name, width=38)
        self.output_box.grid(row=0, column=4, sticky="ew", padx=(0, 8))
        self.output_box.bind("<<ComboboxSelected>>", self.output_selected)
        ttk.Button(top, text="Rescan MIDI", command=self.refresh_outputs_and_open).grid(row=0, column=5, padx=(0, 8))
        self.open_button = ttk.Button(top, text="Reopen Port", command=lambda: self.open_midi(silent=False))
        self.open_button.grid(row=0, column=6)
        ttk.Label(top, text="Default Axis/Trigger Deadzone").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        ttk.Spinbox(top, from_=0.0, to=0.95, increment=0.01, textvariable=self.deadzone, width=8, command=self.deadzone_changed).grid(row=1, column=1, sticky="w", pady=(10, 0))
        ttk.Checkbutton(top, text="Start with Windows", variable=self.start_with_windows, command=self.startup_changed).grid(row=1, column=2, sticky="w", pady=(10, 0))
        ttk.Checkbutton(top, text="Minimize to tray", variable=self.minimize_to_tray, command=self.save_settings).grid(row=1, column=3, sticky="w", pady=(10, 0))
        ttk.Checkbutton(top, text="Start hidden in tray", variable=self.start_minimized_to_tray, command=self.save_settings).grid(row=1, column=4, sticky="w", pady=(10, 0))
        self.midi_state_label = ttk.Label(top, text="MIDI: not open")
        self.midi_state_label.grid(row=1, column=5, columnspan=2, sticky="e", pady=(10, 0))

        learn = ttk.LabelFrame(self, text="Guided Learn Mode", padding=12)
        learn.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))
        learn.columnconfigure(0, weight=1)
        learn.rowconfigure(2, weight=1)
        bar = ttk.Frame(learn)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.learn_button = ttk.Button(bar, text="Start Learn", command=self.toggle_learn)
        self.learn_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Checkbutton(bar, text="Keep learning after each control", variable=self.continuous).grid(row=0, column=1, padx=(0, 16))
        ttk.Button(bar, text="Test Selected", command=self.test_selected).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(bar, text="Delete Selected", command=self.delete_selected).grid(row=0, column=3)
        ttk.Label(learn, textvariable=self.learn_text, font=("Segoe UI", 12)).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        cols = ("label", "kind", "cc", "channel", "mode", "invert", "deadzone", "enabled", "key")
        self.tree = ttk.Treeview(learn, columns=cols, show="headings", selectmode="browse")
        names = {"label": "Control", "kind": "Type", "cc": "CC", "channel": "Ch", "mode": "Mode", "invert": "Invert", "deadzone": "Deadzone", "enabled": "On", "key": "Internal Key"}
        widths = {"label": 220, "kind": 80, "cc": 60, "channel": 60, "mode": 100, "invert": 70, "deadzone": 90, "enabled": 60, "key": 240}
        for c in cols:
            self.tree.heading(c, text=names[c])
            self.tree.column(c, width=widths[c], anchor="center")
        self.tree.column("label", anchor="w")
        self.tree.column("key", anchor="w")
        self.tree.grid(row=2, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", self.edit_selected)
        vsb = ttk.Scrollbar(learn, orient="vertical", command=self.tree.yview)
        vsb.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        bottom = ttk.Frame(self, padding=(14, 0, 14, 12))
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.columnconfigure(4, weight=1)
        ttk.Button(bottom, text="New Profile", command=self.new_profile).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(bottom, text="Load Profile", command=self.load_profile).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(bottom, text="Save Profile", command=self.save_profile).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(bottom, text="Save As", command=self.save_profile_as).grid(row=0, column=3, padx=(0, 16))
        ttk.Label(bottom, textvariable=self.status).grid(row=0, column=4, sticky="e")

    def update_midi_state(self):
        if hasattr(self, "midi_state_label"):
            if self.midi.is_open():
                self.midi_state_label.configure(text=f"MIDI: open ({self.midi.name})")
            else:
                self.midi_state_label.configure(text="MIDI: not open")

    def startup_changed(self):
        try:
            set_start_with_windows(self.start_with_windows.get())
            self.save_settings()
        except Exception as exc:
            messagebox.showerror("Start with Windows", str(exc))
            self.start_with_windows.set(False)
            self.save_settings()

    def start_backends(self):
        errors = []
        try:
            self.gamepads.start()
        except Exception as exc:
            errors.append(str(exc))
        if mido is None:
            errors.append(f"mido import failed: {MIDO_ERROR}")
        if pystray is None:
            errors.append("pystray/Pillow not available; tray mode disabled")
        if errors:
            messagebox.showwarning("Startup warning", "Some features may not work yet.\n\n" + "\n".join(errors) + "\n\nRun: pip install -r requirements.txt")

    def refresh_all(self):
        self.refresh_controllers()
        self.refresh_outputs()
        self.refresh_table()

    def refresh_controllers(self):
        self.gamepads.refresh()
        names = self.gamepads.names()
        self.controller_box["values"] = names or ["No controller found"]
        self.controller_box.current(0)
        self.status.set(f"Found {len(names)} controller(s)." if names else "No controller found.")

    def refresh_outputs(self):
        outs = self.midi.outputs()
        self.output_box["values"] = outs
        if outs:
            preferred = self.output_name.get() if self.output_name.get() in outs else next((o for o in outs if "loopmidi" in o.lower()), outs[0])
            self.output_name.set(preferred)
            self.status.set(f"Found {len(outs)} MIDI output(s).")
        else:
            self.status.set("No MIDI outputs found. Create a loopMIDI port, then rescan.")
        self.update_midi_state()

    def refresh_outputs_and_open(self):
        self.refresh_outputs()
        self.auto_open_midi()

    def output_selected(self, _event=None):
        self.save_settings()
        self.auto_open_midi()

    def auto_open_midi(self, silent=True):
        name = self.output_name.get().strip()
        outputs = self.midi.outputs()
        if not name and outputs:
            name = next((o for o in outputs if "loopmidi" in o.lower()), outputs[0])
            self.output_name.set(name)
        if not name:
            self.update_midi_state()
            return False
        if self.midi.is_open() and self.midi.name == name:
            self.update_midi_state()
            return True
        return self.open_midi(silent=silent)

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for key, m in sorted(self.profile.mappings().items(), key=lambda kv: kv[1].cc):
            self.tree.insert("", "end", iid=key, values=(m.label, m.kind, m.cc, m.channel + 1, m.mode, "Yes" if m.invert else "No", f"{m.deadzone:.2f}", "Yes" if m.enabled else "No", m.key))

    def controller_selected(self, _e=None):
        self.controller_index.set(max(0, self.controller_box.current()))

    def current_joy(self):
        return self.gamepads.get(self.controller_index.get())

    def open_midi(self, silent=False):
        try:
            self.midi.open(self.output_name.get())
            self.profile.data["midi_output_name"] = self.output_name.get()
            self.save_settings()
            self.status.set(f"MIDI output open: {self.output_name.get()}")
            self.update_midi_state()
            return True
        except Exception as exc:
            self.update_midi_state()
            self.status.set(f"MIDI output not open: {exc}")
            if not silent:
                messagebox.showerror("MIDI output error", str(exc))
            return False

    def deadzone_changed(self):
        self.profile.data["axis_deadzone"] = max(0.0, min(0.95, float(self.deadzone.get())))
        self.status.set(f"Default axis/trigger deadzone: {self.profile.data['axis_deadzone']:.2f}")

    def toggle_learn(self):
        self.learning.set(not self.learning.get())
        self.learn_button.configure(text="Stop Learn" if self.learning.get() else "Start Learn")
        self.learn_text.set("Learning: press a button, move an axis, or tap the D-pad." if self.learning.get() else "Learn stopped. Double-click a row to edit it.")
        if self.learning.get() and not self.midi.is_open():
            self.auto_open_midi()

    def event_to_control(self, event):
        if event.type == pygame.JOYBUTTONDOWN:
            return f"button_{event.button}", "button", f"Button {event.button}", 127
        if event.type == pygame.JOYBUTTONUP:
            return f"button_{event.button}", "button", f"Button {event.button}", 0
        if event.type == pygame.JOYAXISMOTION:
            raw = float(event.value)
            if self.learning.get() and abs(raw) < 0.45:
                return None
            return f"axis_{event.axis}", "axis", f"Axis/Trigger {event.axis}", raw
        if event.type == pygame.JOYHATMOTION:
            h = int(event.hat)
            x, y = event.value
            prev = self.hat_previous.get(h, (0, 0))
            self.hat_previous[h] = (x, y)
            if x == 1:
                return f"hat_{h}_right", "hat", f"D-pad {h} Right", 127
            if x == -1:
                return f"hat_{h}_left", "hat", f"D-pad {h} Left", 127
            if y == 1:
                return f"hat_{h}_up", "hat", f"D-pad {h} Up", 127
            if y == -1:
                return f"hat_{h}_down", "hat", f"D-pad {h} Down", 127
            if prev[0] == 1:
                return f"hat_{h}_right", "hat", f"D-pad {h} Right", 0
            if prev[0] == -1:
                return f"hat_{h}_left", "hat", f"D-pad {h} Left", 0
            if prev[1] == 1:
                return f"hat_{h}_up", "hat", f"D-pad {h} Up", 0
            if prev[1] == -1:
                return f"hat_{h}_down", "hat", f"D-pad {h} Down", 0
        return None

    def learn(self, key, kind, label):
        existing = self.profile.mappings().get(key)
        if existing:
            self.tree.selection_set(key)
            return existing
        cc = self.profile.next_cc()
        mapping = Mapping(key=key, kind=kind, label=label, cc=cc, mode="absolute" if kind == "axis" else "momentary", deadzone=float(self.deadzone.get()))
        self.profile.set(mapping)
        self.profile.bump_cc(cc)
        self.refresh_table()
        self.tree.selection_set(key)
        self.learn_text.set(f"Mapped {label} -> MIDI CC {cc}. Press the next control.")
        if not self.continuous.get():
            self.learning.set(False)
            self.learn_button.configure(text="Start Learn")
        return mapping

    def process(self, mapping: Mapping, value: Any):
        if not mapping.enabled:
            return
        if not self.midi.is_open():
            self.auto_open_midi(silent=True)
        if mapping.kind == "axis":
            raw = float(value)
            raw = 0.0 if abs(raw) < mapping.deadzone else raw
            raw = -raw if mapping.invert else raw
            lo, hi = sorted((mapping.min_value, mapping.max_value))
            midi_value = max(0, min(127, round(lo + ((raw + 1.0) / 2.0) * (hi - lo))))
            if self.axis_last.get(mapping.key) != midi_value:
                self.axis_last[mapping.key] = midi_value
                self.midi.cc(mapping.cc, midi_value, mapping.channel)
                self.status.set(f"{mapping.label} -> CC {mapping.cc} value {midi_value}")
            return
        pressed = int(value) > 0
        if mapping.mode == "toggle":
            if pressed:
                state = not self.toggle_state.get(mapping.key, False)
                self.toggle_state[mapping.key] = state
                self.midi.cc(mapping.cc, mapping.max_value if state else mapping.min_value, mapping.channel)
        else:
            self.midi.cc(mapping.cc, mapping.max_value if pressed else mapping.min_value, mapping.channel)

    def poll(self):
        try:
            if pygame and self.gamepads.ready:
                for event in pygame.event.get():
                    if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                        self.refresh_controllers()
                        continue
                    item = self.event_to_control(event)
                    if item:
                        key, kind, label, value = item
                        mapping = self.learn(key, kind, label) if self.learning.get() else self.profile.mappings().get(key)
                        if mapping:
                            self.process(mapping, value)
        finally:
            self.after(8, self.poll)

    def selected_key(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def edit_selected(self, _e=None):
        key = self.selected_key()
        mapping = self.profile.mappings().get(key) if key else None
        if mapping:
            editor = MappingEditor(self, mapping)
            self.wait_window(editor)
            if editor.result:
                self.profile.set(editor.result)
                self.refresh_table()

    def delete_selected(self):
        key = self.selected_key()
        if key:
            self.profile.delete(key)
            self.refresh_table()

    def test_selected(self):
        key = self.selected_key()
        mapping = self.profile.mappings().get(key) if key else None
        if not mapping:
            messagebox.showinfo("Test mapping", "Select a mapping first.")
            return
        if not self.midi.is_open():
            self.auto_open_midi()
        self.midi.cc(mapping.cc, mapping.max_value, mapping.channel)
        self.after(120, lambda: self.midi.cc(mapping.cc, mapping.min_value, mapping.channel))

    def new_profile(self):
        self.profile.new()
        self.profile_path = None
        self.refresh_table()
        self.save_settings()

    def load_profile(self):
        path = filedialog.askopenfilename(title="Load profile", filetypes=[("JSON profiles", "*.json"), ("All files", "*.*")])
        if path:
            self.load_profile_path(Path(path), silent=False)

    def load_last_profile(self):
        last = self.settings.get("last_profile", "")
        if last and Path(last).exists():
            self.load_profile_path(Path(last), silent=True)

    def load_profile_path(self, path: Path, silent=False):
        try:
            self.profile.load(path)
            self.profile_path = path
            self.output_name.set(self.profile.data.get("midi_output_name", self.output_name.get()))
            self.deadzone.set(float(self.profile.data.get("axis_deadzone", 0.08)))
            self.refresh_table()
            self.save_settings()
            self.status.set(f"Loaded profile: {path.name}")
            self.after(100, self.auto_open_midi)
        except Exception as exc:
            if not silent:
                messagebox.showerror("Load profile", str(exc))

    def save_profile(self):
        if self.profile_path is None:
            self.save_profile_as()
            return
        self.write_profile(self.profile_path)

    def save_profile_as(self):
        path = filedialog.asksaveasfilename(title="Save profile as", initialdir=str(PROFILE_DIR), initialfile="controller_profile.json", defaultextension=".json", filetypes=[("JSON profiles", "*.json"), ("All files", "*.*")])
        if path:
            self.profile_path = Path(path)
            self.write_profile(self.profile_path)

    def write_profile(self, path: Path):
        joy = self.current_joy()
        if joy:
            self.profile.data["device_name"] = joy.get_name()
        self.profile.data["midi_output_name"] = self.output_name.get()
        self.profile.data["axis_deadzone"] = float(self.deadzone.get())
        self.profile.save(path)
        self.save_settings()
        self.status.set(f"Saved profile: {path.name}")
        self.auto_open_midi()

    def tray_image(self):
        ico = resource_path("app_icon.ico")
        png = resource_path("app_icon.png")
        if Image:
            for path in (ico, png):
                if path.exists():
                    try:
                        return Image.open(path)
                    except Exception:
                        pass
            img = Image.new("RGBA", (64, 64), (172, 88, 231, 255))
            d = ImageDraw.Draw(img)
            d.rectangle((4, 4, 60, 60), outline=(73, 181, 230, 255), width=6)
            d.text((16, 22), "J2M", fill=(73, 181, 230, 255))
            return img
        return None

    def hide_to_tray(self):
        if not self.minimize_to_tray.get():
            return
        self.withdraw()
        if pystray is None:
            return
        if self.tray_icon is None:
            menu = pystray.Menu(
                pystray.MenuItem("Show joy2midi", lambda: self.after(0, self.show_from_tray), default=True),
                pystray.MenuItem("Exit", lambda: self.after(0, self.exit_app)),
            )
            self.tray_icon = pystray.Icon(APP_NAME, self.tray_image(), APP_NAME, menu)
            self.tray_icon.run_detached()

    def show_from_tray(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.deiconify()
        self.lift()
        self.focus_force()

    def on_unmap(self, _e=None):
        if self.state() == "iconic" and self.minimize_to_tray.get():
            self.after(100, self.hide_to_tray)

    def close_or_tray(self):
        if self.minimize_to_tray.get() and not self.exiting:
            self.hide_to_tray()
        else:
            self.exit_app()

    def exit_app(self):
        self.exiting = True
        self.save_settings()
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.midi.close()
        self.gamepads.stop()
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
