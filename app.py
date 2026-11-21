import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import os
import sys
import threading
import time
import csv
import ctypes
import shutil
from datetime import datetime

import cv2

# ── Work from the folder the app lives in ──────────────
# (so data/ and logs/ sit next to app.py or the .exe)
BASE_DIR = os.path.dirname(
    sys.executable if getattr(sys, "frozen", False)
    else os.path.abspath(__file__))
os.chdir(BASE_DIR)

# ── Paths & settings ───────────────────────────────────
MODEL_PATH           = "data/trainer.yml"
CASCADE_PATH         = cv2.data.haarcascades + \
                       "haarcascade_frontalface_default.xml"
LOG_PATH             = "logs/activity_log.csv"
USERNAME_PATH        = "data/username.txt"
CONFIDENCE_THRESHOLD = 80
LOCK_TIMEOUT         = 5
ADMIN_PASSWORD       = "admin123"
CURRENT_USER         = "Unknown"

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# ── Design tokens (6-digit hex only: Tkinter has no alpha) ──
C = {
    "bg":        "#0d0d14",
    "bg2":       "#0f0f1a",
    "bg3":       "#080810",
    "card":      "#12121e",
    "border":    "#1e1e2e",
    "border2":   "#2a2a3e",
    "accent":    "#6c63ff",
    "accent2":   "#a78bfa",
    "green":     "#22c55e",
    "green_dim": "#0d2e1a",
    "red":       "#ef4444",
    "red_dim":   "#2e0d0d",
    "amber":     "#f59e0b",
    "amber_dim": "#2e200d",
    "text":      "#e8e8f0",
    "muted":     "#6b6b8a",
    "dim":       "#2a2a3e",
    "sidebar":   "#080810",
}


# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════
def load_username():
    global CURRENT_USER
    if os.path.exists(USERNAME_PATH):
        with open(USERNAME_PATH, "r") as f:
            name = f.read().strip()
            if name:
                CURRENT_USER = name


def save_username(name):
    global CURRENT_USER
    CURRENT_USER = name
    with open(USERNAME_PATH, "w") as f:
        f.write(name)


def log_event(event_type, detail=""):
    """Log row: timestamp, user, event, detail."""
    with open(LOG_PATH, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            CURRENT_USER, event_type, detail])


def count_today(event="MONITOR_START"):
    if not os.path.exists(LOG_PATH):
        return 0
    today = datetime.now().strftime("%Y-%m-%d")
    with open(LOG_PATH, "r") as f:
        return sum(1 for r in csv.reader(f)
                   if len(r) >= 3 and r[0].startswith(today)
                   and r[2] == event)


def lock_workstation():
    log_event("LOCK_TRIGGERED", "Absence exceeded threshold")
    ctypes.windll.user32.LockWorkStation()


def make_card(parent, **kwargs):
    return tk.Frame(parent, bg=C["card"],
                    highlightbackground=C["border"],
                    highlightthickness=1, **kwargs)


def label(parent, text, size=11, weight="normal",
          color=None, bg=None, **kwargs):
    return tk.Label(parent, text=text,
                    font=("Segoe UI", size, weight),
                    bg=bg if bg is not None else parent["bg"],
                    fg=color or C["text"], **kwargs)


def flat_button(parent, text, command, bg, fg,
                size=10, weight="bold", border=True):
    return tk.Button(
        parent, text=text, command=command,
        font=("Segoe UI", size, weight),
        bg=bg, fg=fg,
        activebackground=C["border2"],
        activeforeground=C["text"],
        relief="flat", bd=0, cursor="hand2",
        highlightbackground=C["border"],
        highlightthickness=1 if border else 0)


# ══════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════
class Sidebar(tk.Frame):
    def __init__(self, parent, on_select):
        super().__init__(parent, bg=C["sidebar"], width=58,
                         highlightbackground=C["border"],
                         highlightthickness=1)
        self.pack_propagate(False)
        self.on_select = on_select
        self.buttons   = {}

        logo = tk.Canvas(self, width=40, height=40,
                         bg=C["sidebar"], highlightthickness=0)
        logo.pack(pady=(20, 16))
        logo.create_oval(2, 2, 38, 38,
                         fill=C["accent"], outline="")
        logo.create_text(20, 20, text="🔒",
                         font=("Segoe UI Emoji", 16))

        tk.Frame(self, bg=C["border"], height=1).pack(
            fill="x", padx=10, pady=(0, 12))

        for key, icon in [("dashboard", "🛡"), ("enroll", "👤"),
                          ("logs", "📋"), ("settings", "⚙")]:
            c = tk.Canvas(self, width=40, height=40,
                          bg=C["sidebar"],
                          highlightthickness=0, cursor="hand2")
            c.pack(pady=4)
            c.create_text(20, 20, text=icon,
                          font=("Segoe UI Emoji", 18))
            c.bind("<Button-1>",
                   lambda e, k=key: self.select(k))
            self.buttons[key] = c

    def select(self, key):
        for c in self.buttons.values():
            c.configure(bg=C["sidebar"])
        self.buttons[key].configure(bg="#1a1530")
        self.on_select(key)


# ══════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════
class DashboardPage(tk.Frame):
    CAM_W, CAM_H = 360, 190

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._cam_img = None
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Current user ──
        user_card = make_card(body)
        user_card.pack(fill="x", pady=(0, 8))
        u_in = tk.Frame(user_card, bg=C["card"])
        u_in.pack(fill="x", padx=14, pady=8)
        u_left = tk.Frame(u_in, bg=C["card"])
        u_left.pack(side="left")
        label(u_left, "CURRENT USER", 9, color=C["muted"],
              bg=C["card"]).pack(anchor="w")
        self.user_lbl = tk.Label(
            u_left, text=CURRENT_USER,
            font=("Segoe UI", 12, "bold"),
            bg=C["card"], fg=C["accent2"])
        self.user_lbl.pack(anchor="w")
        flat_button(u_in, "✎  Change", self._change_username,
                    C["border"], C["accent2"], size=9,
                    weight="normal", border=False).pack(
                        side="right", ipadx=8, ipady=3)

        # ── Status banner ──
        banner = tk.Frame(body, bg="#0f0a24",
                          highlightbackground="#4a44aa",
                          highlightthickness=1)
        banner.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(banner, bg="#0f0a24")
        inner.pack(fill="x", padx=16, pady=10)

        left = tk.Frame(inner, bg="#0f0a24")
        left.pack(side="left")
        label(left, "SYSTEM STATUS", 9, color=C["muted"],
              bg="#0f0a24").pack(anchor="w")
        self.status_lbl = tk.Label(
            left, text="● INACTIVE",
            font=("Segoe UI", 18, "bold"),
            bg="#0f0a24", fg=C["red"])
        self.status_lbl.pack(anchor="w")
        self.sub_lbl = tk.Label(
            left, text="System is disarmed",
            font=("Segoe UI", 9),
            bg="#0f0a24", fg=C["muted"])
        self.sub_lbl.pack(anchor="w")

        right = tk.Frame(inner, bg="#0f0a24")
        right.pack(side="right")
        self.pulse = tk.Canvas(right, width=44, height=44,
                               bg="#0f0a24", highlightthickness=0)
        self.pulse.pack()
        self.pulse.create_oval(3, 3, 41, 41, outline="#5a1a1a",
                               width=2, tags="ring")
        self.pulse.create_oval(13, 13, 31, 31, fill=C["red"],
                               outline="", tags="dot")

        # ── Confidence bar ──
        conf_card = make_card(body)
        conf_card.pack(fill="x", pady=(0, 8))
        c_in = tk.Frame(conf_card, bg=C["card"])
        c_in.pack(fill="x", padx=14, pady=8)
        top = tk.Frame(c_in, bg=C["card"])
        top.pack(fill="x")
        label(top, "RECOGNITION CONFIDENCE", 9, color=C["muted"],
              bg=C["card"]).pack(side="left")
        self.conf_pct = tk.Label(
            top, text="--", font=("Segoe UI", 9, "bold"),
            bg=C["card"], fg=C["accent2"])
        self.conf_pct.pack(side="right")
        self.bar_canvas = tk.Canvas(c_in, height=8, bg=C["border"],
                                    highlightthickness=0)
        self.bar_canvas.pack(fill="x", pady=(6, 0))
        self.bar_fill = self.bar_canvas.create_rectangle(
            0, 0, 0, 8, fill=C["accent"], outline="")

        # ── Live camera ──
        cam_card = make_card(body)
        cam_card.pack(fill="x", pady=(0, 8))
        self.cam_canvas = tk.Canvas(
            cam_card, width=self.CAM_W, height=self.CAM_H,
            bg=C["bg3"], highlightthickness=0)
        self.cam_canvas.pack(padx=1, pady=1)
        self._show_cam_placeholder("Camera inactive")

        # ── Metrics ──
        row = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x", pady=(0, 8))
        self.metric_vals = {}
        for i, (key, val, name) in enumerate([
                ("timeout", f"{LOCK_TIMEOUT}s", "TIMEOUT"),
                ("sessions", str(count_today()), "SESSIONS"),
                ("locks", str(count_today("LOCK_TRIGGERED")),
                 "LOCKS")]):
            card = make_card(row)
            card.pack(side="left", expand=True, fill="x",
                      padx=(0 if i == 0 else 6, 0))
            v = tk.Label(card, text=val,
                         font=("Segoe UI", 16, "bold"),
                         bg=C["card"],
                         fg=C["accent2"] if key == "timeout"
                         else C["text"])
            v.pack(pady=(8, 0))
            label(card, name, 8, color=C["muted"],
                  bg=C["card"]).pack(pady=(0, 8))
            self.metric_vals[key] = v

        # ── Arm button ──
        self.arm_btn = tk.Button(
            body, text="▶   ARM SYSTEM",
            font=("Segoe UI", 13, "bold"),
            bg=C["green"], fg="white",
            activebackground=C["green"],
            activeforeground="white",
            relief="flat", bd=0, cursor="hand2",
            command=self.app.toggle_monitoring)
        self.arm_btn.pack(fill="x", ipady=11, pady=(0, 8))

        # ── Secondary buttons ──
        row2 = tk.Frame(body, bg=C["bg"])
        row2.pack(fill="x", pady=(0, 6))
        flat_button(row2, "👤  Enroll User", self.app.go_enroll,
                    C["card"], C["accent2"]).pack(
                        side="left", expand=True, fill="x",
                        ipady=8, padx=(0, 4))
        flat_button(row2, "⚙   Settings", self.app.go_settings,
                    C["card"], C["accent2"]).pack(
                        side="left", expand=True, fill="x",
                        ipady=8, padx=(4, 0))
        flat_button(body, "📋   View Activity Log",
                    self.app.go_logs, C["card"],
                    C["accent2"]).pack(fill="x", ipady=8)

    # ── username ──
    def _change_username(self):
        name = simpledialog.askstring(
            "Set Username", "Enter your name:",
            initialvalue=CURRENT_USER if CURRENT_USER != "Unknown"
            else "")
        if name and name.strip():
            save_username(name.strip())
            self.refresh_username()

    def refresh_username(self):
        self.user_lbl.config(text=CURRENT_USER)

    # ── camera area ──
    def _show_cam_placeholder(self, text):
        self.cam_canvas.delete("all")
        self._cam_img = None
        self.cam_canvas.create_text(
            self.CAM_W // 2, self.CAM_H // 2, text=text,
            fill=C["muted"], font=("Segoe UI", 10))

    def update_frame(self, frame, confidence, authorized):
        if not self.app.monitoring:
            return
        from PIL import Image, ImageTk
        frame = cv2.resize(frame, (self.CAM_W, self.CAM_H))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        color = (34, 197, 94) if authorized else (239, 68, 68)
        cv2.putText(frame,
                    "AUTHORIZED" if authorized else "UNAUTHORIZED",
                    (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, color, 2)
        cv2.putText(frame,
                    f"Score: {confidence:.1f}  "
                    f"(threshold < {CONFIDENCE_THRESHOLD})",
                    (10, self.CAM_H - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        self._cam_img = ImageTk.PhotoImage(Image.fromarray(frame))
        self.cam_canvas.delete("all")
        self.cam_canvas.create_image(0, 0, anchor="nw",
                                     image=self._cam_img)

    # ── state ──
    def set_active(self, active):
        if active:
            self.status_lbl.config(text="● ACTIVE", fg=C["green"])
            self.sub_lbl.config(text="Monitoring…")
            self.arm_btn.config(text="⏹   DISARM SYSTEM",
                                bg=C["red"],
                                activebackground=C["red"])
            self._set_pulse(C["green"])
            self._show_cam_placeholder("Starting camera…")
        else:
            self.status_lbl.config(text="● INACTIVE", fg=C["red"])
            self.sub_lbl.config(text="System is disarmed")
            self.arm_btn.config(text="▶   ARM SYSTEM",
                                bg=C["green"],
                                activebackground=C["green"])
            self.conf_pct.config(text="--")
            self._set_pulse(C["red"])
            self._set_bar(0)
            self._show_cam_placeholder("Camera inactive")

    def set_warning(self, secs):
        self.status_lbl.config(
            text=f"⚠  LOCKING IN {secs:.0f}s", fg=C["amber"])
        self.sub_lbl.config(text="No authorized face detected")
        self._set_pulse(C["amber"])

    def set_confidence(self, conf):
        pct = max(0, min(100, int((1 - conf / 150) * 100)))
        self.status_lbl.config(text="● ACTIVE", fg=C["green"])
        self.conf_pct.config(text=f"{pct}% match")
        self.sub_lbl.config(
            text=f"User recognized · score {conf:.1f}")
        self._set_pulse(C["green"])
        self._set_bar(pct)

    def _set_pulse(self, color):
        dim = {C["green"]: C["green_dim"],
               C["red"]: C["red_dim"],
               C["amber"]: C["amber_dim"]}
        self.pulse.itemconfig("ring", outline=dim.get(color,
                                                      C["border"]))
        self.pulse.itemconfig("dot", fill=color)

    def _set_bar(self, pct):
        self.bar_canvas.update_idletasks()
        w = self.bar_canvas.winfo_width()
        self.bar_canvas.coords(self.bar_fill, 0, 0,
                               int(w * pct / 100), 8)

    def refresh_metrics(self):
        self.metric_vals["timeout"].config(text=f"{LOCK_TIMEOUT}s")
        self.metric_vals["sessions"].config(
            text=str(count_today()))
        self.metric_vals["locks"].config(
            text=str(count_today("LOCK_TRIGGERED")))


# ══════════════════════════════════════════════════════
#  ENROLL
# ══════════════════════════════════════════════════════
class EnrollPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=14)

        label(body, "Face Enrollment", 16, "bold").pack(
            pady=(4, 2))
        label(body, "Capture your face from five angles",
              10, color=C["muted"]).pack(pady=(0, 12))

        name_card = make_card(body)
        name_card.pack(fill="x", pady=(0, 10))
        n_in = tk.Frame(name_card, bg=C["card"])
        n_in.pack(fill="x", padx=14, pady=10)
        label(n_in, "YOUR NAME", 9, color=C["muted"],
              bg=C["card"]).pack(anchor="w", pady=(0, 4))
        self.name_var = tk.StringVar(
            value="" if CURRENT_USER == "Unknown"
            else CURRENT_USER)
        tk.Entry(n_in, textvariable=self.name_var,
                 font=("Segoe UI", 11),
                 bg=C["bg2"], fg=C["text"],
                 insertbackground=C["text"], relief="flat",
                 highlightbackground=C["border"],
                 highlightthickness=1).pack(fill="x", ipady=6)

        steps = make_card(body)
        steps.pack(fill="x", pady=(0, 10))
        s_in = tk.Frame(steps, bg=C["card"])
        s_in.pack(fill="x", padx=14, pady=10)
        label(s_in, "ENROLLMENT STEPS", 9, color=C["muted"],
              bg=C["card"]).pack(anchor="w", pady=(0, 6))
        for i, (angle, tip) in enumerate([
                ("Front", "Look straight at camera"),
                ("Left", "Turn head slowly left"),
                ("Right", "Turn head slowly right"),
                ("Up", "Tilt head slightly up"),
                ("Down", "Tilt head slightly down")]):
            r = tk.Frame(s_in, bg=C["card"])
            r.pack(fill="x", pady=2)
            tk.Label(r, text=str(i + 1),
                     font=("Segoe UI", 9, "bold"),
                     bg=C["accent"], fg="white",
                     width=2).pack(side="left", padx=(0, 10))
            tk.Label(r, text=f"{angle} — {tip}",
                     font=("Segoe UI", 10),
                     bg=C["card"], fg=C["text"]).pack(side="left")

        note = tk.Frame(body, bg=C["amber_dim"],
                        highlightbackground="#8a6000",
                        highlightthickness=1)
        note.pack(fill="x", pady=(0, 10))
        tk.Label(note, text="⚠  Press SPACE to capture each angle",
                 font=("Segoe UI", 10), bg=C["amber_dim"],
                 fg=C["amber"]).pack(padx=14, pady=8)

        tk.Button(body, text="▶   Start Enrollment",
                  font=("Segoe UI", 12, "bold"),
                  bg=C["accent"], fg="white",
                  activebackground="#5b52ee",
                  activeforeground="white",
                  relief="flat", bd=0, cursor="hand2",
                  command=self._start).pack(fill="x", ipady=11)

    def _start(self):
        if self.app.monitoring:
            messagebox.showwarning(
                "Active", "Disarm the system before enrolling.")
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning(
                "Name required",
                "Please enter your name before enrolling.")
            return
        if not messagebox.askyesno(
                "Start enrollment",
                f"Enrolling as: {name}\n\n"
                "This replaces the current face model.\n"
                "Continue?"):
            return

        save_username(name)
        self.app.pages["dashboard"].refresh_username()

        self.app.root.withdraw()
        try:
            import enroll
            enroll.enroll_user()
        finally:
            self.app.root.deiconify()

        log_event("USER_ENROLLED", f"User {name} enrolled")
        messagebox.showinfo(
            "Done", f"Enrollment complete for {name}!\n"
                    "You can now arm the system.")


# ══════════════════════════════════════════════════════
#  LOGS
# ══════════════════════════════════════════════════════
class LogsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=12)

        top = tk.Frame(body, bg=C["bg"])
        top.pack(fill="x", pady=(0, 8))
        label(top, "Activity Log", 14, "bold").pack(side="left")
        flat_button(top, "⬇  Download", self._download,
                    C["accent"], "white", size=9,
                    border=False).pack(side="right",
                                       ipadx=8, ipady=3)
        flat_button(top, "↺  Refresh", self.load,
                    C["card"], C["accent2"], size=9,
                    weight="normal").pack(
                        side="right", padx=(0, 8),
                        ipadx=8, ipady=3)

        legend = tk.Frame(body, bg=C["bg"])
        legend.pack(fill="x", pady=(0, 6))
        for color, text in [(C["green"], "Active"),
                            (C["amber"], "Absence"),
                            (C["red"], "Lock")]:
            tk.Label(legend, text="●", font=("Segoe UI", 10),
                     bg=C["bg"], fg=color).pack(side="left")
            tk.Label(legend, text=text + "  ",
                     font=("Segoe UI", 9),
                     bg=C["bg"], fg=C["muted"]).pack(side="left")

        frame = make_card(body)
        frame.pack(fill="both", expand=True)
        vs = tk.Scrollbar(frame)
        vs.pack(side="right", fill="y")
        hs = tk.Scrollbar(frame, orient="horizontal")
        hs.pack(side="bottom", fill="x")
        self.listbox = tk.Listbox(
            frame, bg=C["card"], fg=C["text"],
            font=("Courier New", 9),
            yscrollcommand=vs.set, xscrollcommand=hs.set,
            relief="flat", bd=0, activestyle="none",
            selectbackground=C["border2"])
        self.listbox.pack(fill="both", expand=True,
                          padx=6, pady=6)
        vs.config(command=self.listbox.yview)
        hs.config(command=self.listbox.xview)
        self.load()

    def load(self):
        self.listbox.delete(0, "end")
        if not os.path.exists(LOG_PATH):
            self.listbox.insert("end", "  No logs yet.")
            return
        with open(LOG_PATH, "r") as f:
            rows = [r for r in csv.reader(f) if r]
        if not rows:
            self.listbox.insert("end", "  No logs yet.")
            return
        for row in reversed(rows):
            row = (row + ["", "", "", ""])[:4]
            entry = (f"  {row[0]}  |  {row[1]:<12}|  "
                     f"{row[2]:<18}|  {row[3]}")
            self.listbox.insert("end", entry)
            ev = row[2]
            if "LOCK" in ev or "FAILED" in ev:
                color = C["red"]
            elif "START" in ev or "ENROLLED" in ev:
                color = C["green"]
            elif "ABSENCE" in ev:
                color = C["amber"]
            else:
                color = C["muted"]
            self.listbox.itemconfig("end", fg=color)

    def _download(self):
        if not os.path.exists(LOG_PATH):
            messagebox.showinfo("No logs",
                                "There are no logs to download yet.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"),
                       ("All files", "*.*")],
            initialfile=f"ActivityLog_{stamp}.csv",
            title="Save activity log")
        if not path:
            return
        shutil.copy2(LOG_PATH, path)
        messagebox.showinfo("Downloaded",
                            f"Log saved to:\n{path}")


# ══════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════
class SettingsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.body = tk.Frame(self, bg=C["bg"])
        self.body.pack(fill="both", expand=True,
                       padx=16, pady=14)
        self._show_lock()

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _show_lock(self):
        self._clear()
        canvas = tk.Canvas(self.body, width=60, height=60,
                           bg=C["bg"], highlightthickness=0)
        canvas.pack(pady=(30, 0))
        canvas.create_oval(2, 2, 58, 58, fill=C["border"],
                           outline=C["border2"])
        canvas.create_text(30, 30, text="🔐",
                           font=("Segoe UI Emoji", 24))
        label(self.body, "Admin Access Required", 13,
              "bold").pack(pady=(12, 4))
        label(self.body,
              "Enter the admin password\nto access settings",
              10, color=C["muted"], justify="center").pack(
                  pady=(0, 18))

        self.pwd_var = tk.StringVar()
        entry = tk.Entry(self.body, textvariable=self.pwd_var,
                         show="●", font=("Segoe UI", 12),
                         bg=C["card"], fg=C["text"],
                         insertbackground=C["text"],
                         relief="flat",
                         highlightbackground=C["border"],
                         highlightthickness=1)
        entry.pack(fill="x", ipady=9, pady=(0, 12))
        entry.bind("<Return>", lambda e: self._unlock())
        tk.Button(self.body, text="Unlock Settings",
                  font=("Segoe UI", 11, "bold"),
                  bg=C["accent"], fg="white",
                  activebackground="#5b52ee",
                  activeforeground="white",
                  relief="flat", bd=0, cursor="hand2",
                  command=self._unlock).pack(fill="x", ipady=10)

    def _unlock(self):
        if self.pwd_var.get() != ADMIN_PASSWORD:
            messagebox.showerror("Denied", "Incorrect password.")
            return
        self._show_settings()

    def _show_settings(self):
        self._clear()
        label(self.body, "Settings", 14, "bold").pack(
            anchor="w", pady=(0, 12))

        card = make_card(self.body)
        card.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="x", padx=14, pady=12)

        self.conf_var = tk.IntVar(value=CONFIDENCE_THRESHOLD)
        self.lock_var = tk.IntVar(value=LOCK_TIMEOUT)

        for text, var, lo, hi, suffix in [
                ("Confidence threshold", self.conf_var,
                 20, 150, ""),
                ("Lock timeout", self.lock_var, 3, 30, "s")]:
            r = tk.Frame(inner, bg=C["card"])
            r.pack(fill="x", pady=(0, 10))
            t = tk.Frame(r, bg=C["card"])
            t.pack(fill="x")
            tk.Label(t, text=text, font=("Segoe UI", 10),
                     bg=C["card"], fg=C["text"]).pack(side="left")
            val = tk.Label(t, text=f"{var.get()}{suffix}",
                           font=("Segoe UI", 10, "bold"),
                           bg=C["card"], fg=C["accent2"])
            val.pack(side="right")
            tk.Scale(r, from_=lo, to=hi, orient="horizontal",
                     variable=var, showvalue=False,
                     bg=C["card"], fg=C["muted"],
                     troughcolor=C["border2"],
                     highlightthickness=0,
                     command=lambda _v, v=var, l=val, s=suffix:
                     l.config(text=f"{v.get()}{s}")).pack(fill="x")

        tk.Frame(inner, bg=C["border"], height=1).pack(
            fill="x", pady=(2, 10))
        label(inner, "Change admin password", 10,
              bg=C["card"]).pack(anchor="w", pady=(0, 4))
        self.new_pwd = tk.Entry(inner, show="●",
                                font=("Segoe UI", 10),
                                bg=C["bg2"], fg=C["text"],
                                insertbackground=C["text"],
                                relief="flat",
                                highlightbackground=C["border"],
                                highlightthickness=1)
        self.new_pwd.pack(fill="x", ipady=6)

        row = tk.Frame(self.body, bg=C["bg"])
        row.pack(fill="x")
        tk.Button(row, text="Save Settings",
                  font=("Segoe UI", 11, "bold"),
                  bg=C["accent"], fg="white",
                  activebackground="#5b52ee",
                  activeforeground="white",
                  relief="flat", bd=0, cursor="hand2",
                  command=self._save).pack(
                      side="left", expand=True, fill="x",
                      ipady=10, padx=(0, 6))
        flat_button(row, "Lock", self._show_lock, C["card"],
                    C["muted"], size=11, weight="normal").pack(
                        side="right", ipady=10, ipadx=14)

    def _save(self):
        global CONFIDENCE_THRESHOLD, LOCK_TIMEOUT, ADMIN_PASSWORD
        CONFIDENCE_THRESHOLD = self.conf_var.get()
        LOCK_TIMEOUT         = self.lock_var.get()
        new = self.new_pwd.get().strip()
        if new:
            ADMIN_PASSWORD = new
        log_event("SETTINGS_CHANGED",
                  f"threshold={CONFIDENCE_THRESHOLD},"
                  f"timeout={LOCK_TIMEOUT}")
        self.app.pages["dashboard"].refresh_metrics()
        messagebox.showinfo("Saved", "Settings saved!")


# ══════════════════════════════════════════════════════
#  TOPBAR
# ══════════════════════════════════════════════════════
class Topbar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=C["bg3"],
                         highlightbackground=C["border"],
                         highlightthickness=1, height=52)
        self.pack_propagate(False)
        inner = tk.Frame(self, bg=C["bg3"])
        inner.pack(fill="both", expand=True, padx=14)
        tk.Label(inner, text="Biometric Protection System",
                 font=("Segoe UI", 11, "bold"),
                 bg=C["bg3"], fg=C["text"]).pack(
                     side="left", pady=14)
        self.badge = tk.Label(inner, text="● INACTIVE",
                              font=("Segoe UI", 9, "bold"),
                              bg=C["red_dim"], fg=C["red"],
                              padx=10, pady=3)
        self.badge.pack(side="right", pady=14)

    def set_status(self, active, warning=False):
        if warning:
            self.badge.config(text="⚠ WARNING",
                              bg=C["amber_dim"], fg=C["amber"])
        elif active:
            self.badge.config(text="● ACTIVE",
                              bg=C["green_dim"], fg=C["green"])
        else:
            self.badge.config(text="● INACTIVE",
                              bg=C["red_dim"], fg=C["red"])


# ══════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════
class BiometricApp:
    def __init__(self, root):
        self.root       = root
        self.monitoring = False
        load_username()

        root.title("Biometric Protection System")
        root.geometry("500x800")
        root.resizable(False, False)
        root.configure(bg=C["bg"])
        self._build()

    def _build(self):
        self.topbar = Topbar(self.root)
        self.topbar.pack(fill="x")

        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill="both", expand=True)

        # Pages first (they live in an unpacked container)...
        self.container = tk.Frame(main, bg=C["bg"])
        self.pages = {
            "dashboard": DashboardPage(self.container, self),
            "enroll":    EnrollPage(self.container, self),
            "logs":      LogsPage(self.container, self),
            "settings":  SettingsPage(self.container, self),
        }

        # ...then sidebar packs BEFORE the container so it
        # always keeps its space on every page.
        self.sidebar = Sidebar(main, self._on_nav)
        self.sidebar.pack(side="left", fill="y")
        self.container.pack(side="left", fill="both",
                            expand=True)

        self.sidebar.select("dashboard")

    def _on_nav(self, key):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        if key == "logs":
            self.pages["logs"].load()
        if key == "dashboard":
            self.pages["dashboard"].refresh_metrics()

    def go_enroll(self):   self.sidebar.select("enroll")
    def go_settings(self): self.sidebar.select("settings")
    def go_logs(self):     self.sidebar.select("logs")

    # ── arm / disarm ───────────────────────────────────
    def toggle_monitoring(self):
        dash = self.pages["dashboard"]

        if not self.monitoring:
            if not os.path.exists(MODEL_PATH):
                messagebox.showerror(
                    "No model", "Please enroll a user first.")
                return
            if CURRENT_USER == "Unknown":
                name = simpledialog.askstring(
                    "Username required",
                    "Please enter your name before arming:")
                if not name or not name.strip():
                    return
                save_username(name.strip())
                dash.refresh_username()

            self.monitoring = True
            log_event("MONITOR_START", f"Armed by {CURRENT_USER}")
            dash.set_active(True)
            dash.refresh_metrics()
            self.topbar.set_status(True)
            threading.Thread(target=self._monitor_loop,
                             daemon=True).start()
        else:
            pwd = simpledialog.askstring(
                "Disarm system",
                "Enter admin password to disarm:", show="●")
            if pwd is None:
                return
            if pwd != ADMIN_PASSWORD:
                messagebox.showerror(
                    "Access denied",
                    "Incorrect password.\nOnly an authorized "
                    "user can disarm the system.")
                log_event("DISARM_FAILED",
                          "Incorrect password attempt")
                return
            self.monitoring = False
            log_event("MONITOR_STOP",
                      f"Disarmed by {CURRENT_USER}")
            dash.set_active(False)
            dash.refresh_metrics()
            self.topbar.set_status(False)

    # ── background monitoring thread ───────────────────
    def _monitor_loop(self):
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(MODEL_PATH)
        cascade = cv2.CascadeClassifier(CASCADE_PATH)
        cam = cv2.VideoCapture(0)
        dash = self.pages["dashboard"]

        if not cam.isOpened():
            self.monitoring = False
            self.root.after(0, lambda: (
                messagebox.showerror("Webcam",
                                     "Cannot access webcam."),
                dash.set_active(False),
                self.topbar.set_status(False)))
            return

        absence_start = None

        while self.monitoring:
            ret, frame = cam.read()
            if not ret:
                break

            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(
                gray, scaleFactor=1.3, minNeighbors=5)

            authorized = False
            best_conf  = None

            for (x, y, w, h) in faces:
                _, conf = recognizer.predict(gray[y:y + h,
                                                  x:x + w])
                ok = conf < CONFIDENCE_THRESHOLD
                if best_conf is None or conf < best_conf:
                    best_conf = conf
                if ok:
                    authorized = True
                cv2.rectangle(
                    frame, (x, y), (x + w, y + h),
                    (34, 197, 94) if ok else (239, 68, 68), 2)

            if authorized:
                absence_start = None
                self.root.after(
                    0, lambda c=best_conf: (
                        dash.set_confidence(c),
                        self.topbar.set_status(True)))
            else:
                if absence_start is None:
                    absence_start = time.time()
                    log_event("ABSENCE_DETECTED")
                remaining = max(
                    0, LOCK_TIMEOUT - (time.time() - absence_start))
                self.root.after(
                    0, lambda r=remaining: (
                        dash.set_warning(r),
                        self.topbar.set_status(True,
                                               warning=True)))

            self.root.after(
                0, lambda f=frame.copy(),
                c=best_conf if best_conf is not None else 0.0,
                a=authorized: dash.update_frame(f, c, a))

            if (not authorized and
                    time.time() - absence_start >= LOCK_TIMEOUT):
                cam.release()
                self.monitoring = False
                self.root.after(0, self._on_locked)
                lock_workstation()
                return

            time.sleep(0.15)

        cam.release()

    def _on_locked(self):
        dash = self.pages["dashboard"]
        dash.set_active(False)
        dash.refresh_metrics()
        self.topbar.set_status(False)


if __name__ == "__main__":
    root = tk.Tk()
    BiometricApp(root)
    root.mainloop()
