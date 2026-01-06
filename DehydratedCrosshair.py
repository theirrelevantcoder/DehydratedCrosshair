import os
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import sys, os

def base_dir():
    # When built with PyInstaller, files live next to the EXE (onedir)
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = base_dir()

# Optional Pillow for banner image. App still runs without it.
try:
    from PIL import Image, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False

APP_NAME = "Dehydrated Crosshair"
OVERLAY_EXE_NAME = "CrosshairOverlay.exe"
OVERLAY_JSON_NAME = "overlay_settings.json"
APP_SETTINGS_NAME = "app_settings.json"
BANNER_FILE = "Dehydrated_Crosshair_Banner.png"

STYLE_CHOICES_UI = ["Dot", "Plus", "Cross"]
STYLE_MAP_TO_JSON = {"Dot": "dot", "Plus": "plus", "Cross": "cross"}
STYLE_MAP_FROM_JSON = {v: k for k, v in STYLE_MAP_TO_JSON.items()}

COLOR_CHOICES_UI = ["White", "Red", "Green", "Blue"]
COLOR_MAP_TO_JSON = {"White": "white", "Red": "red", "Green": "green", "Blue": "blue"}
COLOR_MAP_FROM_JSON = {v: k for k, v in COLOR_MAP_TO_JSON.items()}

def app_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def atomic_write_json(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

class SettingsModel:
    def __init__(self):
        # crosshair
        self.enabled = False
        self.style_ui = "Dot"
        self.size = 6               # for dot: radius; for lines: half-length
        self.thickness = 2
        self.outline = 0
        self.color_ui = "White"
        self.opacity = 1.0

        # app
        self.dark_mode = True

    def to_overlay_json(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "style": STYLE_MAP_TO_JSON.get(self.style_ui, "dot"),
            "size": int(self.size),
            "thickness": int(self.thickness),
            "outline": int(self.outline),
            "color": COLOR_MAP_TO_JSON.get(self.color_ui, "white"),
            "opacity": float(max(0.0, min(1.0, self.opacity))),
        }

    def load(self):
        p = os.path.join(app_dir(), APP_SETTINGS_NAME)
        if not os.path.exists(p):
            return
        try:
            data = json.load(open(p, "r", encoding="utf-8"))
        except Exception:
            return
        self.enabled = bool(data.get("enabled", self.enabled))
        self.style_ui = data.get("style_ui", self.style_ui)
        self.size = int(data.get("size", self.size))
        self.thickness = int(data.get("thickness", self.thickness))
        self.outline = int(data.get("outline", self.outline))
        self.color_ui = data.get("color_ui", self.color_ui)
        self.opacity = float(data.get("opacity", self.opacity))
        self.dark_mode = bool(data.get("dark_mode", self.dark_mode))

    def save(self):
        p = os.path.join(app_dir(), APP_SETTINGS_NAME)
        data = {
            "enabled": bool(self.enabled),
            "style_ui": self.style_ui,
            "size": int(self.size),
            "thickness": int(self.thickness),
            "outline": int(self.outline),
            "color_ui": self.color_ui,
            "opacity": float(self.opacity),
            "dark_mode": bool(self.dark_mode),
        }
        atomic_write_json(p, data)

class OverlayController:
    def __init__(self, model: SettingsModel):
        self.model = model
        self.proc = None

    def overlay_exe_path(self) -> str:
        return os.path.join(app_dir(), OVERLAY_EXE_NAME)

    def overlay_json_path(self) -> str:
        return os.path.join(app_dir(), OVERLAY_JSON_NAME)

    def ensure_overlay_running(self):
        exe = self.overlay_exe_path()
        if not os.path.exists(exe):
            raise FileNotFoundError(f"Missing {OVERLAY_EXE_NAME} next to the .py file.")
        if self.proc is not None and self.proc.poll() is None:
            return
        # Start overlay detached (no console). It will read overlay_settings.json from cwd.
        self.proc = subprocess.Popen(
            [exe],
            cwd=app_dir(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )

    def write_overlay_settings(self):
        atomic_write_json(self.overlay_json_path(), self.model.to_overlay_json())

    def set_enabled(self, enabled: bool):
        self.model.enabled = bool(enabled)
        if self.model.enabled:
            self.ensure_overlay_running()
        self.write_overlay_settings()

    def shutdown(self):
        # Disable crosshair first so if overlay lingers, it's invisible.
        try:
            self.model.enabled = False
            self.write_overlay_settings()
        except Exception:
            pass
        try:
            if self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.resizable(False, False)

        self.model = SettingsModel()
        self.model.load()
        self.overlay = OverlayController(self.model)

        self.banner_photo = None

        # Always ensure overlay_settings.json exists
        try:
            self.overlay.write_overlay_settings()
        except Exception:
            pass

        self._build_styles()
        self._build_ui()
        self._apply_theme()

        # Start overlay if enabled (but do not force enable)
        if self.model.enabled:
            try:
                self.overlay.ensure_overlay_running()
                self.overlay.write_overlay_settings()
            except Exception:
                # Don't block launch
                self.model.enabled = False

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- UI ----------
    def _build_styles(self):
        self.style = ttk.Style()
        # Use a platform theme that supports colors (clam is consistent)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

    def _apply_theme(self):
        dark = bool(self.model.dark_mode)
        bg = "#151515" if dark else "#f2f2f2"
        panel = "#1e1e1e" if dark else "#ffffff"
        btn = "#2a2a2a" if dark else "#e7e7e7"
        btn_active = "#333333" if dark else "#dcdcdc"
        fg = "#ffffff" if dark else "#111111"
        subfg = "#cfcfcf" if dark else "#333333"
        accent = "#ff7a18"

        self.colors = dict(bg=bg, panel=panel, btn=btn, btn_active=btn_active, fg=fg, subfg=subfg, accent=accent)

        self.root.configure(bg=bg)

        self.style.configure("TFrame", background=bg)
        self.style.configure("Panel.TFrame", background=panel)
        self.style.configure("Title.TLabel", background=bg, foreground=fg, font=("Segoe UI", 14, "bold"))
        self.style.configure("Sub.TLabel", background=bg, foreground=subfg, font=("Segoe UI", 9))
        self.style.configure("TLabel", background=panel, foreground=fg, font=("Segoe UI", 10))
        self.style.configure("TButton", background=btn, foreground=fg, padding=(12, 10), font=("Segoe UI", 10, "bold"))
        self.style.map("TButton",
                       background=[("active", btn_active), ("pressed", btn_active)],
                       foreground=[("disabled", "#777777")])

        self.style.configure("TCombobox", padding=(8, 6))
        self.style.configure("Horizontal.TScale", background=panel)

        # update accent bar if present
        try:
            if hasattr(self, 'accent_bar') and self.accent_bar is not None:
                self.accent_bar.configure(bg=accent)
        except Exception:
            pass

        # repaint frames
        self.header.configure(style="TFrame")
        self.card.configure(style="Panel.TFrame")
        self.title.configure(style="Title.TLabel")
        self.subtitle.configure(style="Sub.TLabel")
        self._refresh_toggle_text()

    def _build_ui(self):
        self.header = ttk.Frame(self.root)
        self.header.pack(fill="x", padx=14, pady=(14, 8))

        # Banner (optional). File: Dehydrated_Crosshair_Banner.png (400x80)
        banner_bg = "#151515" if bool(self.model.dark_mode) else "#f2f2f2"
        banner_path = os.path.join(app_dir(), BANNER_FILE)
        if PIL_OK and os.path.exists(banner_path):
            try:
                img = Image.open(banner_path)
                img = img.resize((400, 80), Image.Resampling.LANCZOS)
                self.banner_photo = ImageTk.PhotoImage(img)
                tk.Label(self.header, image=self.banner_photo, bg=banner_bg).pack(anchor="w", pady=(0, 8))
            except Exception:
                self.banner_photo = None

        self.title = ttk.Label(self.header, text="Version 1.0", style="Title.TLabel")
        self.title.pack(anchor="w")

        self.subtitle = ttk.Label(self.header, text="the nonkoreanspywarefree crosshair brought to you by void", style="Sub.TLabel")
        self.subtitle.pack(anchor="w", pady=(2, 10))
        # Accent bar (color finalized in _apply_theme)
        self.accent_bar = tk.Frame(self.header, height=3, bg="#ff7a18")
        self.accent_bar.pack(fill="x", anchor="w")

        self.card = ttk.Frame(self.root, style="Panel.TFrame")
        self.card.pack(fill="both", padx=14, pady=(0, 14))

        self.btn_toggle = ttk.Button(self.card, text="Toggle Crosshair", command=self.on_toggle)
        self.btn_toggle.pack(fill="x", padx=14, pady=(14, 8))

        ttk.Button(self.card, text="Raid Planner", command=self.open_raid_planner).pack(fill="x", padx=14, pady=8)
        ttk.Button(self.card, text="Raid Calculator", command=self.open_raid_calculator).pack(fill="x", padx=14, pady=8)

        ttk.Button(self.card, text="Settings", command=self.open_settings).pack(fill="x", padx=14, pady=8)
        ttk.Button(self.card, text="Save Settings", command=self.on_save).pack(fill="x", padx=14, pady=8)

        ttk.Button(self.card, text="Dark / Light Mode", command=self.toggle_darkmode).pack(fill="x", padx=14, pady=8)
        ttk.Button(self.card, text="Exit", command=self.on_close).pack(fill="x", padx=14, pady=(8, 14))

        self._refresh_toggle_text()

    def _refresh_toggle_text(self):
        txt = "Crosshair: ON (click to turn OFF)" if self.model.enabled else "Crosshair: OFF (click to turn ON)"
        try:
            self.btn_toggle.configure(text=txt)
        except Exception:
            pass

    # ---------- Actions ----------
    def on_toggle(self):
        try:
            self.overlay.set_enabled(not self.model.enabled)
            self._refresh_toggle_text()
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    def on_save(self):
        try:
            self.model.save()
            messagebox.showinfo(APP_NAME, "Saved.")
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    def toggle_darkmode(self):
        self.model.dark_mode = not self.model.dark_mode
        self._apply_theme()

    def on_close(self):
        try:
            self.model.save()
        except Exception:
            pass
        try:
            self.overlay.shutdown()
        except Exception:
            pass
        self.root.destroy()
    # ---------- Raid tools ----------
    _RAID_TABLE = {
        "Wood Wall":    {"Rockets": 2,  "C4": 1, "Satchels": 4,  "Explosive Ammo": 49},
        "Stone Wall":   {"Rockets": 4,  "C4": 2, "Satchels": 10, "Explosive Ammo": 185},
        "Metal Wall":   {"Rockets": 8,  "C4": 4, "Satchels": 23, "Explosive Ammo": 400},
        "Armored Wall": {"Rockets": 15, "C4": 8, "Satchels": 46, "Explosive Ammo": 799},
        "Sheet Door":   {"Rockets": 2,  "C4": 1, "Satchels": 4,  "Explosive Ammo": 63},
        "Garage Door":  {"Rockets": 3,  "C4": 2, "Satchels": 9,  "Explosive Ammo": 150},
        "Armored Door": {"Rockets": 5,  "C4": 3, "Satchels": 15, "Explosive Ammo": 280},
    }

    _COSTS = {
        "Rockets":        {"sulfur": 1400, "gp": 650},
        "C4":             {"sulfur": 2200, "gp": 1000},
        "Satchels":       {"sulfur": 480,  "gp": 240},
        "Explosive Ammo": {"sulfur": 25,   "gp": 10},
    }

    def _fmt(self, n: int) -> str:
        try:
            return f"{int(n):,}"
        except Exception:
            return str(n)

    def open_raid_planner(self):
        win = tk.Toplevel(self.root)
        win.title("Raid Planner")
        win.resizable(False, False)

        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True, padx=14, pady=14)

        ttk.Label(outer, text="Raid Planner", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Quick reference for common raid costs (approx).").pack(anchor="w", pady=(2, 10))

        row = ttk.Frame(outer)
        row.pack(fill="x", pady=(0, 10))

        ttk.Label(row, text="Structure").pack(side="left")
        structure_var = tk.StringVar(value=list(self._RAID_TABLE.keys())[0])
        ttk.Combobox(row, textvariable=structure_var, values=list(self._RAID_TABLE.keys()),
                    state="readonly", width=26).pack(side="right")

        out = tk.Text(outer, width=56, height=10, state="disabled",
                      font=("Consolas", 10), borderwidth=0, highlightthickness=1)
        out.pack(fill="both", expand=False)

        def refresh(*_):
            struct = structure_var.get()
            data = self._RAID_TABLE.get(struct, {})
            out.config(state="normal")
            out.delete("1.0", "end")
            out.insert("end", f"{struct}\n")
            out.insert("end", "-" * 50 + "\n")
            for k in ["Rockets", "C4", "Satchels", "Explosive Ammo"]:
                out.insert("end", f"{k:<16} : {data.get(k, '-')}\n")
            out.config(state="disabled")

        structure_var.trace_add("write", refresh)
        refresh()

        ttk.Button(outer, text="Close", command=win.destroy).pack(anchor="e", pady=(10, 0))

    def open_raid_calculator(self):
        win = tk.Toplevel(self.root)
        win.title("Raid Calculator")
        win.resizable(False, False)

        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True, padx=14, pady=14)

        ttk.Label(outer, text="Raid Calculator", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Estimate sulfur + gunpowder totals.").pack(anchor="w", pady=(2, 10))

        grid = ttk.Frame(outer)
        grid.pack(fill="x", pady=(0, 10))

        ttk.Label(grid, text="Structure").grid(row=0, column=0, sticky="w")
        structure_var = tk.StringVar(value=list(self._RAID_TABLE.keys())[0])
        ttk.Combobox(grid, textvariable=structure_var, values=list(self._RAID_TABLE.keys()),
                    state="readonly", width=22).grid(row=0, column=1, sticky="w", padx=(8, 18))

        ttk.Label(grid, text="Method").grid(row=0, column=2, sticky="w")
        method_var = tk.StringVar(value="Rockets")
        ttk.Combobox(grid, textvariable=method_var, values=list(self._COSTS.keys()),
                    state="readonly", width=18).grid(row=0, column=3, sticky="w", padx=(8, 0))

        ttk.Label(grid, text="Count").grid(row=1, column=0, sticky="w", pady=(10, 0))
        count_var = tk.IntVar(value=1)
        ttk.Spinbox(grid, from_=1, to=999, textvariable=count_var, width=8)\
            .grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        out = tk.Text(outer, width=56, height=12, state="disabled",
                      font=("Consolas", 10), borderwidth=0, highlightthickness=1)
        out.pack(fill="both", expand=False)

        def refresh(*_):
            struct = structure_var.get()
            method = method_var.get()
            cnt = max(1, int(count_var.get()))

            per_piece = int(self._RAID_TABLE.get(struct, {}).get(method, 0))
            total_needed = per_piece * cnt

            cost = self._COSTS.get(method, {"sulfur": 0, "gp": 0})
            sulfur_direct = int(cost["sulfur"] * total_needed)
            gp = int(cost["gp"] * total_needed)

            sulfur_for_gp = gp * 2
            charcoal = gp
            sulfur_total = sulfur_direct + sulfur_for_gp

            out.config(state="normal")
            out.delete("1.0", "end")
            out.insert("end", f"Target: {struct} x{cnt}\n")
            out.insert("end", f"Method: {method}\n")
            out.insert("end", f"Total Needed: {total_needed}\n")
            out.insert("end", "-" * 50 + "\n")
            out.insert("end", "Est. Materials:\n")
            out.insert("end", f"  Sulfur (direct): {self._fmt(sulfur_direct)}\n")
            out.insert("end", f"  Gunpowder:       {self._fmt(gp)}\n")
            out.insert("end", f"  Charcoal:        {self._fmt(charcoal)}\n")
            out.insert("end", f"  Sulfur (for GP): {self._fmt(sulfur_for_gp)}\n")
            out.insert("end", f"  Sulfur total:    {self._fmt(sulfur_total)}\n")
            out.config(state="disabled")

        structure_var.trace_add("write", refresh)
        method_var.trace_add("write", refresh)
        count_var.trace_add("write", refresh)
        refresh()

        ttk.Button(outer, text="Close", command=win.destroy).pack(anchor="e", pady=(10, 0))

    # ---------- Settings window ----------
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.resizable(False, False)
        win.configure(bg=self.colors["bg"])

        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True, padx=14, pady=14)

        panel = ttk.Frame(outer, style="Panel.TFrame")
        panel.pack(fill="both", expand=True)

        # Variables
        style_var = tk.StringVar(value=self.model.style_ui)
        color_var = tk.StringVar(value=self.model.color_ui)
        size_var = tk.IntVar(value=int(self.model.size))
        outline_var = tk.IntVar(value=int(self.model.outline))
        opacity_var = tk.DoubleVar(value=float(self.model.opacity))

        def push_to_overlay():
            # Update model from vars
            self.model.style_ui = style_var.get()
            self.model.color_ui = color_var.get()
            self.model.size = int(size_var.get())
            self.model.outline = int(outline_var.get())
            self.model.opacity = float(opacity_var.get())

            # Live update: write JSON every move (atomic replace)
            try:
                # keep enabled state as-is; if enabled, ensure overlay running
                if self.model.enabled:
                    self.overlay.ensure_overlay_running()
                self.overlay.write_overlay_settings()
            except Exception:
                # Don't spam dialogs while dragging sliders
                pass

        # Layout helpers
        def row(label: str):
            fr = ttk.Frame(panel, style="Panel.TFrame")
            fr.pack(fill="x", padx=14, pady=(12, 0))
            ttk.Label(fr, text=label).pack(anchor="w")
            return fr

        # Style
        fr = row("Style")
        cb = ttk.Combobox(fr, textvariable=style_var, values=STYLE_CHOICES_UI, state="readonly")
        cb.pack(fill="x", pady=(6, 0))
        style_var.trace_add("write", lambda *_: push_to_overlay())

        # Size
        fr = row("Size")
        sc = ttk.Scale(fr, from_=2, to=40, orient="horizontal",
                       command=lambda v: (size_var.set(int(float(v))), push_to_overlay()))
        sc.set(size_var.get())
        sc.pack(fill="x", pady=(6, 0))
        # Thickness control removed (core overlay stable)

        # Color
        fr = row("Color")
        cb2 = ttk.Combobox(fr, textvariable=color_var, values=COLOR_CHOICES_UI, state="readonly")
        cb2.pack(fill="x", pady=(6, 0))
        color_var.trace_add("write", lambda *_: push_to_overlay())

        # Opacity
        fr = row("Opacity")
        sc3 = ttk.Scale(fr, from_=0.05, to=1.0, orient="horizontal",
                        command=lambda v: (opacity_var.set(float(v)), push_to_overlay()))
        sc3.set(opacity_var.get())
        sc3.pack(fill="x", pady=(6, 0))

        # Outline
        fr = row("Outline / Border")
        sc4 = ttk.Scale(fr, from_=0, to=8, orient="horizontal",
                        command=lambda v: (outline_var.set(int(float(v))), push_to_overlay()))
        sc4.set(outline_var.get())
        sc4.pack(fill="x", pady=(6, 0))

        # Footer buttons
        footer = ttk.Frame(panel, style="Panel.TFrame")
        footer.pack(fill="x", padx=14, pady=14)

        ttk.Button(footer, text="Close", command=win.destroy).pack(side="right")

        # Apply theme to child widgets
        # (ttk uses style; background already set)
        try:
            win.grab_set()
        except Exception:
            pass

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
