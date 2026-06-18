"""PyInstaller runtime hook for joy2midi.

Forces Mido to use the python-rtmidi backend inside the frozen EXE.
Without this, the normal Python version may see MIDI ports while the
PyInstaller EXE returns an empty MIDI output list.
"""

import os

os.environ.setdefault("MIDO_BACKEND", "mido.backends.rtmidi")
