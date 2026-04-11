"""ScrcpyRelauncher – A tkinter GUI wrapper for scrcpy."""

import json
import os
import re
import shlex
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULTS = {
    "serial": "",
    "window_title": "",
    "max_size": "0",
    "max_fps": "60",
    "video_bit_rate": "8M",
    "video_codec": "h264",
    "video_source": "display",
    "camera_id": "",
    "camera_facing": "",
    "camera_size": "",
    "camera_fps": "",
    "audio_source": "output",
    "no_audio": False,
    "no_control": False,
    "turn_screen_off": False,
    "stay_awake": False,
    "always_on_top": False,
    "fullscreen": False,
    "borderless": False,
    "show_touches": False,
    "power_off_on_close": False,
    "crop": "",
    "display_orientation": "0",
    "record_file": "",
    "record_format": "",
    "verbosity": "info",
    "extra_args": "",
    "relaunch_on_termination": False,
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            merged = {**DEFAULTS, **saved}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULTS)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


class ScrcpyRelauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scrcpy Relauncher")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._process: subprocess.Popen | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitor = threading.Event()

        self.cfg = load_config()

        # Camera data: {camera_id: {"facing": str, "sizes": [str], "fps": [str]}}
        self._camera_info: dict[str, dict] = {}

        self._build_gui()
        self._load_values()
        self._refresh_devices()

    # ── GUI construction ────────────────────────────────────────────

    def _build_gui(self):
        pad = {"padx": 5, "pady": 2}
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        row = 0

        # ── Device & Window ─────────────────────────────────────────
        lf_device = ttk.LabelFrame(main, text="Device & Window")
        lf_device.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        ttk.Label(lf_device, text="Device:").grid(row=0, column=0, sticky="w", **pad)
        self.var_serial = tk.StringVar()
        self.cb_serial = ttk.Combobox(lf_device, textvariable=self.var_serial, width=36)
        self.cb_serial.grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(lf_device, text="Refresh", width=8, command=self._refresh_devices).grid(
            row=0, column=2, **pad)

        ttk.Label(lf_device, text="Window title:").grid(row=1, column=0, sticky="w", **pad)
        self.var_window_title = tk.StringVar()
        ttk.Entry(lf_device, textvariable=self.var_window_title, width=30).grid(row=1, column=1, sticky="ew", **pad)

        lf_device.columnconfigure(1, weight=1)

        # ── Video ───────────────────────────────────────────────────
        lf_video = ttk.LabelFrame(main, text="Video")
        lf_video.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        vr = 0
        ttk.Label(lf_video, text="Max resolution:").grid(row=vr, column=0, sticky="w", **pad)
        self.var_max_size = tk.StringVar()
        self.cb_max_size = ttk.Combobox(lf_video, textvariable=self.var_max_size, width=12,
                                        values=["0", "480", "720", "1080", "1440", "2160"])
        self.cb_max_size.grid(row=vr, column=1, sticky="w", **pad)

        ttk.Label(lf_video, text="Max FPS:").grid(row=vr, column=2, sticky="w", **pad)
        self.var_max_fps = tk.StringVar()
        self.cb_max_fps = ttk.Combobox(lf_video, textvariable=self.var_max_fps, width=8,
                                       values=["15", "24", "30", "60", "120"])
        self.cb_max_fps.grid(row=vr, column=3, sticky="w", **pad)

        vr += 1
        ttk.Label(lf_video, text="Bit rate:").grid(row=vr, column=0, sticky="w", **pad)
        self.var_video_bit_rate = tk.StringVar()
        self.cb_video_bit_rate = ttk.Combobox(lf_video, textvariable=self.var_video_bit_rate, width=12,
                                              values=["2M", "4M", "8M", "16M", "32M"])
        self.cb_video_bit_rate.grid(row=vr, column=1, sticky="w", **pad)

        ttk.Label(lf_video, text="Codec:").grid(row=vr, column=2, sticky="w", **pad)
        self.var_video_codec = tk.StringVar()
        self.cb_video_codec = ttk.Combobox(lf_video, textvariable=self.var_video_codec, width=8,
                                           values=["h264", "h265", "av1"], state="readonly")
        self.cb_video_codec.grid(row=vr, column=3, sticky="w", **pad)

        vr += 1
        ttk.Label(lf_video, text="Video source:").grid(row=vr, column=0, sticky="w", **pad)
        self.var_video_source = tk.StringVar()
        self.cb_video_source = ttk.Combobox(lf_video, textvariable=self.var_video_source, width=12,
                                            values=["display", "camera"], state="readonly")
        self.cb_video_source.grid(row=vr, column=1, sticky="w", **pad)
        self.var_video_source.trace_add("write", self._on_video_source_changed)

        ttk.Label(lf_video, text="Orientation:").grid(row=vr, column=2, sticky="w", **pad)
        self.var_display_orientation = tk.StringVar()
        self.cb_display_orientation = ttk.Combobox(lf_video, textvariable=self.var_display_orientation, width=8,
                                                   values=["0", "90", "180", "270"], state="readonly")
        self.cb_display_orientation.grid(row=vr, column=3, sticky="w", **pad)

        # ── Camera ──────────────────────────────────────────────────
        self.lf_camera = ttk.LabelFrame(main, text="Camera (video-source=camera)")
        self.lf_camera.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        cr = 0
        ttk.Label(self.lf_camera, text="Camera:").grid(row=cr, column=0, sticky="w", **pad)
        self.var_camera_id = tk.StringVar()
        self.cb_camera_id = ttk.Combobox(self.lf_camera, textvariable=self.var_camera_id, width=30, state="readonly")
        self.cb_camera_id.grid(row=cr, column=1, sticky="w", **pad)
        self.var_camera_id.trace_add("write", self._on_camera_id_changed)

        ttk.Button(self.lf_camera, text="Refresh", width=8, command=self._refresh_cameras).grid(
            row=cr, column=2, **pad)

        ttk.Label(self.lf_camera, text="Facing:").grid(row=cr, column=3, sticky="w", **pad)
        self.var_camera_facing = tk.StringVar()
        self.cb_camera_facing = ttk.Combobox(self.lf_camera, textvariable=self.var_camera_facing, width=10,
                                             values=["", "front", "back", "external"], state="readonly")
        self.cb_camera_facing.grid(row=cr, column=4, sticky="w", **pad)

        cr += 1
        ttk.Label(self.lf_camera, text="Resolution:").grid(row=cr, column=0, sticky="w", **pad)
        self.var_camera_size = tk.StringVar()
        self.cb_camera_size = ttk.Combobox(self.lf_camera, textvariable=self.var_camera_size, width=14, state="readonly")
        self.cb_camera_size.grid(row=cr, column=1, sticky="w", **pad)

        ttk.Label(self.lf_camera, text="FPS:").grid(row=cr, column=3, sticky="w", **pad)
        self.var_camera_fps = tk.StringVar()
        self.cb_camera_fps = ttk.Combobox(self.lf_camera, textvariable=self.var_camera_fps, width=8, state="readonly")
        self.cb_camera_fps.grid(row=cr, column=4, sticky="w", **pad)

        # ── Audio ───────────────────────────────────────────────────
        lf_audio = ttk.LabelFrame(main, text="Audio")
        lf_audio.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        ttk.Label(lf_audio, text="Audio source:").grid(row=0, column=0, sticky="w", **pad)
        self.var_audio_source = tk.StringVar()
        self.cb_audio_source = ttk.Combobox(
            lf_audio, textvariable=self.var_audio_source, width=22, state="readonly",
            values=["output", "playback", "mic", "mic-unprocessed", "mic-camcorder",
                    "mic-voice-recognition", "mic-voice-communication"])
        self.cb_audio_source.grid(row=0, column=1, sticky="w", **pad)

        self.var_no_audio = tk.BooleanVar()
        ttk.Checkbutton(lf_audio, text="No audio", variable=self.var_no_audio).grid(
            row=0, column=2, sticky="w", **pad)

        # ── Behaviour checkboxes ────────────────────────────────────
        lf_behaviour = ttk.LabelFrame(main, text="Behaviour")
        lf_behaviour.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        self.var_no_control = tk.BooleanVar()
        self.var_turn_screen_off = tk.BooleanVar()
        self.var_stay_awake = tk.BooleanVar()
        self.var_always_on_top = tk.BooleanVar()
        self.var_fullscreen = tk.BooleanVar()
        self.var_borderless = tk.BooleanVar()
        self.var_show_touches = tk.BooleanVar()
        self.var_power_off_on_close = tk.BooleanVar()

        checks = [
            (self.var_no_control, "No control (read-only)"),
            (self.var_turn_screen_off, "Turn screen off"),
            (self.var_stay_awake, "Stay awake"),
            (self.var_always_on_top, "Always on top"),
            (self.var_fullscreen, "Fullscreen"),
            (self.var_borderless, "Borderless"),
            (self.var_show_touches, "Show touches"),
            (self.var_power_off_on_close, "Power off on close"),
        ]
        for i, (var, text) in enumerate(checks):
            r, c = divmod(i, 4)
            ttk.Checkbutton(lf_behaviour, text=text, variable=var).grid(
                row=r, column=c, sticky="w", **pad)

        # ── Recording ──────────────────────────────────────────────
        lf_rec = ttk.LabelFrame(main, text="Recording")
        lf_rec.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        ttk.Label(lf_rec, text="Record file:").grid(row=0, column=0, sticky="w", **pad)
        self.var_record_file = tk.StringVar()
        ttk.Entry(lf_rec, textvariable=self.var_record_file, width=28).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(lf_rec, text="Browse…", command=self._browse_record_file).grid(row=0, column=2, **pad)

        ttk.Label(lf_rec, text="Format:").grid(row=0, column=3, sticky="w", **pad)
        self.var_record_format = tk.StringVar()
        self.cb_record_format = ttk.Combobox(lf_rec, textvariable=self.var_record_format, width=8,
                                             values=["", "mp4", "mkv", "m4a", "mka"], state="readonly")
        self.cb_record_format.grid(row=0, column=4, sticky="w", **pad)
        lf_rec.columnconfigure(1, weight=1)

        # ── Advanced ────────────────────────────────────────────────
        lf_adv = ttk.LabelFrame(main, text="Advanced")
        lf_adv.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        ttk.Label(lf_adv, text="Crop (W:H:X:Y):").grid(row=0, column=0, sticky="w", **pad)
        self.var_crop = tk.StringVar()
        ttk.Entry(lf_adv, textvariable=self.var_crop, width=18).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(lf_adv, text="Verbosity:").grid(row=0, column=2, sticky="w", **pad)
        self.var_verbosity = tk.StringVar()
        self.cb_verbosity = ttk.Combobox(lf_adv, textvariable=self.var_verbosity, width=10,
                                         values=["verbose", "debug", "info", "warn", "error"], state="readonly")
        self.cb_verbosity.grid(row=0, column=3, sticky="w", **pad)

        ttk.Label(lf_adv, text="Extra args:").grid(row=1, column=0, sticky="w", **pad)
        self.var_extra_args = tk.StringVar()
        ttk.Entry(lf_adv, textvariable=self.var_extra_args, width=50).grid(
            row=1, column=1, columnspan=3, sticky="ew", **pad)

        lf_adv.columnconfigure(3, weight=1)

        # ── Process controls ────────────────────────────────────────
        lf_ctrl = ttk.LabelFrame(main, text="Process Control")
        lf_ctrl.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        btn_frame = ttk.Frame(lf_ctrl)
        btn_frame.grid(row=0, column=0, columnspan=4, sticky="ew", **pad)

        self.btn_launch = ttk.Button(btn_frame, text="Launch", command=self._launch)
        self.btn_launch.pack(side="left", padx=4)

        self.btn_relaunch = ttk.Button(btn_frame, text="Relaunch", command=self._relaunch)
        self.btn_relaunch.pack(side="left", padx=4)

        self.btn_close = ttk.Button(btn_frame, text="Close", command=self._close_process)
        self.btn_close.pack(side="left", padx=4)

        self.var_relaunch_on_termination = tk.BooleanVar()
        ttk.Checkbutton(btn_frame, text="Relaunch on termination",
                        variable=self.var_relaunch_on_termination).pack(side="left", padx=12)

        self.var_status = tk.StringVar(value="Stopped")
        self.lbl_status = ttk.Label(btn_frame, textvariable=self.var_status, foreground="red",
                                    font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side="right", padx=8)

        # ── Command preview ─────────────────────────────────────────
        lf_preview = ttk.LabelFrame(main, text="Command Preview")
        lf_preview.grid(row=row, column=0, columnspan=2, sticky="ew", **pad)
        row += 1

        self.txt_preview = tk.Text(lf_preview, height=2, wrap="word", state="disabled",
                                   background="#f0f0f0", font=("Consolas", 9))
        self.txt_preview.grid(row=0, column=0, sticky="ew", **pad)
        lf_preview.columnconfigure(0, weight=1)

        ttk.Button(lf_preview, text="Refresh preview", command=self._update_preview).grid(
            row=0, column=1, **pad)

        # initial state
        self._on_video_source_changed()
        self._update_button_states()

    # ── Config ↔ GUI ────────────────────────────────────────────────

    def _load_values(self):
        c = self.cfg
        self.var_serial.set(c["serial"])
        self.var_window_title.set(c["window_title"])
        self.var_max_size.set(c["max_size"])
        self.var_max_fps.set(c["max_fps"])
        self.var_video_bit_rate.set(c["video_bit_rate"])
        self.var_video_codec.set(c["video_codec"])
        self.var_video_source.set(c["video_source"])
        self.var_camera_id.set(c["camera_id"])
        self.var_camera_facing.set(c["camera_facing"])
        self.var_camera_size.set(c["camera_size"])
        self.var_camera_fps.set(c["camera_fps"])
        self.var_audio_source.set(c["audio_source"])
        self.var_no_audio.set(c["no_audio"])
        self.var_no_control.set(c["no_control"])
        self.var_turn_screen_off.set(c["turn_screen_off"])
        self.var_stay_awake.set(c["stay_awake"])
        self.var_always_on_top.set(c["always_on_top"])
        self.var_fullscreen.set(c["fullscreen"])
        self.var_borderless.set(c["borderless"])
        self.var_show_touches.set(c["show_touches"])
        self.var_power_off_on_close.set(c["power_off_on_close"])
        self.var_crop.set(c["crop"])
        self.var_display_orientation.set(c["display_orientation"])
        self.var_record_file.set(c["record_file"])
        self.var_record_format.set(c["record_format"])
        self.var_verbosity.set(c["verbosity"])
        self.var_extra_args.set(c["extra_args"])
        self.var_relaunch_on_termination.set(c["relaunch_on_termination"])

    def _gather_values(self) -> dict:
        return {
            "serial": self.var_serial.get().strip(),
            "window_title": self.var_window_title.get().strip(),
            "max_size": self.var_max_size.get().strip(),
            "max_fps": self.var_max_fps.get().strip(),
            "video_bit_rate": self.var_video_bit_rate.get().strip(),
            "video_codec": self.var_video_codec.get(),
            "video_source": self.var_video_source.get(),
            "camera_id": self.var_camera_id.get().split(" ")[0] if self.var_camera_id.get() else "",
            "camera_facing": self.var_camera_facing.get(),
            "camera_size": self.var_camera_size.get().strip(),
            "camera_fps": self.var_camera_fps.get().strip(),
            "audio_source": self.var_audio_source.get(),
            "no_audio": self.var_no_audio.get(),
            "no_control": self.var_no_control.get(),
            "turn_screen_off": self.var_turn_screen_off.get(),
            "stay_awake": self.var_stay_awake.get(),
            "always_on_top": self.var_always_on_top.get(),
            "fullscreen": self.var_fullscreen.get(),
            "borderless": self.var_borderless.get(),
            "show_touches": self.var_show_touches.get(),
            "power_off_on_close": self.var_power_off_on_close.get(),
            "crop": self.var_crop.get().strip(),
            "display_orientation": self.var_display_orientation.get(),
            "record_file": self.var_record_file.get().strip(),
            "record_format": self.var_record_format.get(),
            "verbosity": self.var_verbosity.get(),
            "extra_args": self.var_extra_args.get().strip(),
            "relaunch_on_termination": self.var_relaunch_on_termination.get(),
        }

    # ── Command builder ─────────────────────────────────────────────

    def _build_command(self, cfg: dict | None = None) -> list[str]:
        if cfg is None:
            cfg = self._gather_values()

        cmd = ["scrcpy"]

        serial = cfg["serial"].split()[0] if cfg["serial"] else ""
        if serial:
            cmd += ["--serial", serial]
        if cfg["window_title"]:
            cmd += ["--window-title", cfg["window_title"]]
        if cfg["video_bit_rate"] and cfg["video_bit_rate"] != "8M":
            cmd += ["--video-bit-rate", cfg["video_bit_rate"]]
        if cfg["video_codec"] and cfg["video_codec"] != "h264":
            cmd += ["--video-codec", cfg["video_codec"]]
        if cfg["video_source"] == "camera":
            cmd += ["--video-source=camera"]
            if cfg["camera_id"]:
                cmd += ["--camera-id", cfg["camera_id"]]
            if cfg["camera_facing"]:
                cmd += ["--camera-facing", cfg["camera_facing"]]
            if cfg["camera_size"]:
                cmd += ["--camera-size", cfg["camera_size"]]
            if cfg["camera_fps"]:
                cmd += ["--camera-fps", cfg["camera_fps"]]
        else:
            if cfg["max_size"] and cfg["max_size"] != "0":
                cmd += ["--max-size", cfg["max_size"]]
            if cfg["max_fps"]:
                cmd += ["--max-fps", cfg["max_fps"]]
        if cfg["display_orientation"] and cfg["display_orientation"] != "0":
            cmd += ["--display-orientation", cfg["display_orientation"]]
        if cfg["audio_source"] and cfg["audio_source"] != "output":
            cmd += ["--audio-source", cfg["audio_source"]]
        if cfg["no_audio"]:
            cmd.append("--no-audio")
        if cfg["crop"]:
            cmd += ["--crop", cfg["crop"]]
        if cfg["verbosity"] and cfg["verbosity"] != "info":
            cmd += ["--verbosity", cfg["verbosity"]]
        if cfg["record_file"]:
            cmd += ["--record", cfg["record_file"]]
            if cfg["record_format"]:
                cmd += ["--record-format", cfg["record_format"]]

        # boolean flags
        flag_map = {
            "no_control": "--no-control",
            "turn_screen_off": "--turn-screen-off",
            "stay_awake": "--stay-awake",
            "always_on_top": "--always-on-top",
            "fullscreen": "--fullscreen",
            "borderless": "--window-borderless",
            "show_touches": "--show-touches",
            "power_off_on_close": "--power-off-on-close",
        }
        for key, flag in flag_map.items():
            if cfg[key]:
                cmd.append(flag)

        if cfg["extra_args"]:
            cmd += shlex.split(cfg["extra_args"])

        return cmd

    # ── Process management ──────────────────────────────────────────

    def _launch(self):
        if self._process and self._process.poll() is None:
            messagebox.showinfo("Already running", "scrcpy is already running. Use Relaunch to restart.")
            return

        cfg = self._gather_values()
        save_config(cfg)
        self.cfg = cfg

        cmd = self._build_command(cfg)
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except FileNotFoundError:
            messagebox.showerror("scrcpy not found",
                                 "Could not find 'scrcpy' on PATH.\n"
                                 "Make sure scrcpy is installed and accessible.")
            return
        except Exception as exc:
            messagebox.showerror("Launch error", str(exc))
            return

        self._set_status("Running", "green")
        self._start_monitor()
        self._update_button_states()

    def _relaunch(self):
        self._set_status("Restarting…", "orange")
        self._close_process(relaunch=True)
        self.after(300, self._launch)

    def _close_process(self, relaunch=False):
        if not relaunch:
            # Temporarily disable auto-relaunch so the monitor thread doesn't restart
            self._stop_monitor.set()

        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

        self._process = None
        if not relaunch:
            self._set_status("Stopped", "red")
            self._update_button_states()

    def _start_monitor(self):
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self):
        while not self._stop_monitor.is_set():
            if self._process is None:
                return
            ret = self._process.poll()
            if ret is not None:
                # Process has exited
                if self.var_relaunch_on_termination.get() and not self._stop_monitor.is_set():
                    self.after(0, self._set_status, "Restarting…", "orange")
                    self.after(500, self._launch)
                else:
                    self.after(0, self._set_status, f"Exited (code {ret})", "red")
                    self.after(0, self._update_button_states)
                return
            self._stop_monitor.wait(0.5)

    def _set_status(self, text: str, color: str):
        self.var_status.set(text)
        self.lbl_status.configure(foreground=color)

    def _update_button_states(self):
        running = self._process is not None and self._process.poll() is None
        self.btn_launch.configure(state="disabled" if running else "normal")
        self.btn_relaunch.configure(state="normal" if running else "disabled")
        self.btn_close.configure(state="normal" if running else "disabled")

    # ── Helpers ─────────────────────────────────────────────────────

    def _on_video_source_changed(self, *_args):
        is_camera = self.var_video_source.get() == "camera"
        state = "readonly" if is_camera else "disabled"
        entry_state = "normal" if is_camera else "disabled"
        for child in self.lf_camera.winfo_children():
            try:
                if isinstance(child, ttk.Combobox):
                    child.configure(state=state)
                elif isinstance(child, (ttk.Entry, ttk.Button)):
                    child.configure(state=entry_state)
            except tk.TclError:
                pass

    def _refresh_devices(self):
        """Query `adb devices` and populate the device dropdown."""
        try:
            result = subprocess.run(
                ["adb", "devices", "-l"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            lines = result.stdout.strip().splitlines()[1:]  # skip header
            devices = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                serial = parts[0]
                status = parts[1] if len(parts) > 1 else ""
                # Extract model name if present
                model = ""
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1]
                        break
                label = serial
                if model:
                    label = f"{serial}  ({model})"
                if status != "device":
                    label += f"  [{status}]"
                devices.append(label)
            self.cb_serial["values"] = devices
            # If current value not in list and devices available, select first
            current = self.var_serial.get().strip()
            serials = [d.split()[0] for d in devices]
            if current not in serials and devices:
                self.var_serial.set(devices[0])
        except FileNotFoundError:
            messagebox.showerror("adb not found", "Could not find 'adb' on PATH.")
        except Exception as exc:
            messagebox.showerror("adb error", str(exc))

    def _get_selected_serial(self) -> str:
        """Extract the plain serial from the device dropdown value."""
        val = self.var_serial.get().strip()
        return val.split()[0] if val else ""

    def _refresh_cameras(self):
        """Query `scrcpy --list-camera-sizes` and populate camera dropdowns."""
        serial = self._get_selected_serial()
        cmd = ["scrcpy", "--list-camera-sizes"]
        if serial:
            cmd += ["--serial", serial]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            output = result.stdout + result.stderr  # scrcpy outputs to stderr
        except FileNotFoundError:
            messagebox.showerror("scrcpy not found", "Could not find 'scrcpy' on PATH.")
            return
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        self._camera_info.clear()
        current_cam: str | None = None
        in_high_speed = False

        for line in output.splitlines():
            # Match camera header: --camera-id=0    (back, 4032x3024, fps=[15, 30, 60])
            m = re.match(
                r"\s*--camera-id=(\d+)\s+\(([^,]+),\s*([^,]+),\s*fps=\[([^\]]+)\]",
                line,
            )
            if m:
                cam_id = m.group(1)
                facing = m.group(2).strip()
                native_size = m.group(3).strip()
                fps_list = [f.strip() for f in m.group(4).split(",")]
                self._camera_info[cam_id] = {
                    "facing": facing,
                    "native_size": native_size,
                    "sizes": [],
                    "fps": fps_list,
                }
                current_cam = cam_id
                in_high_speed = False
                continue

            # Detect high-speed section (skip those sizes)
            if "High speed" in line:
                in_high_speed = True
                continue

            # Match resolution line:  - 1920x1080
            if current_cam and not in_high_speed:
                m2 = re.match(r"\s+-\s+(\d+x\d+)\s*$", line)
                if m2:
                    self._camera_info[current_cam]["sizes"].append(m2.group(1))

        # Populate camera ID dropdown
        cam_labels = []
        for cid, info in self._camera_info.items():
            cam_labels.append(f"{cid} — {info['facing']} ({info['native_size']})")
        self.cb_camera_id["values"] = cam_labels

        if cam_labels:
            # Try to keep current selection, otherwise pick first
            current_id = self.var_camera_id.get().split(" ")[0] if self.var_camera_id.get() else ""
            if current_id not in self._camera_info:
                self.var_camera_id.set(cam_labels[0])
            self._on_camera_id_changed()

    def _on_camera_id_changed(self, *_args):
        """Update resolution and FPS dropdowns when camera selection changes."""
        cam_id = self.var_camera_id.get().split(" ")[0] if self.var_camera_id.get() else ""
        info = self._camera_info.get(cam_id)
        if info:
            self.cb_camera_size["values"] = info["sizes"]
            self.cb_camera_fps["values"] = info["fps"]
            # Auto-select first available if current is invalid
            if self.var_camera_size.get() not in info["sizes"] and info["sizes"]:
                self.var_camera_size.set(info["sizes"][0])
            if self.var_camera_fps.get() not in info["fps"] and info["fps"]:
                self.var_camera_fps.set(info["fps"][0])
        else:
            self.cb_camera_size["values"] = []
            self.cb_camera_fps["values"] = []

    def _browse_record_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4"), ("MKV", "*.mkv"), ("All", "*.*")])
        if path:
            self.var_record_file.set(path)

    def _update_preview(self):
        cmd = self._build_command()
        text = shlex.join(cmd)
        self.txt_preview.configure(state="normal")
        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("1.0", text)
        self.txt_preview.configure(state="disabled")

    def _on_close(self):
        # Save current values before closing
        try:
            save_config(self._gather_values())
        except Exception:
            pass
        self._stop_monitor.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()
        self.destroy()


if __name__ == "__main__":
    app = ScrcpyRelauncher()
    app.mainloop()
