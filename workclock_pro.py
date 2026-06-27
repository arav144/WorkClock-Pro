import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import time
from datetime import datetime
from datetime import datetime, timezone
import threading
import pytz
import os
import sys
ist = pytz.timezone("Asia/Kolkata")
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

import socket
import uuid as _uuid_mod

try:
    from PIL import Image
    import pystray
    from pystray import MenuItem as item
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


APP_NAME        = "WorkClock Pro"
APP_VERSION     = "v2.0"
SECRET_CODE     = None  
TARGET_HOURS    = 9.0   


SUPABASE_URL="https://example.supabase.co"
SUPABASE_KEY="your_supabase_anon_key_here"


_sb = None

def sb():

    global _sb
    if _sb is None and SUPABASE_AVAILABLE:
        try:
            _sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"Supabase init error: {e}")
    return _sb

def get_device_id():    
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                    for i in range(0,48,8)][::-1])
    hostname = socket.gethostname()
    return f"{hostname}-{mac}"


import uuid

def fetch_config_from_supabase():

    global SECRET_CODE, TARGET_HOURS
    client = sb()
    if not client:
        SECRET_CODE = None  # No internet = no override allowed
        return
    try:
        res = client.table("app_config").select("key,value").execute()
        for row in res.data:
            if row["key"] == "secret_code":
                SECRET_CODE = row["value"]
            elif row["key"] == "target_hours":
                TARGET_HOURS = float(row["value"])
        print(f"Config loaded from Supabase — target: {TARGET_HOURS}h")
    except Exception as e:
        SECRET_CODE = None  
        print(f"Config fetch failed: {e}")

def ensure_employee_registered(name: str) -> str | None:  
    client = sb()
    if not client:
        return None
    device_id = get_device_id()
    try:
     
        res = client.table("employees").select("id").eq("device_id", device_id).execute()
        if res.data:
            return res.data[0]["id"]
        # Register new
        ins = client.table("employees").insert({
            "name":      name,
            "device_id": device_id,
            "is_active": True
        }).execute()
        return ins.data[0]["id"] if ins.data else None
    except Exception as e:
        print(f"Employee register error: {e}")
        return None

def upload_log_start(employee_id: str, employee_name: str, task: str, date_str: str, start_dt) -> str | None:
   
    client = sb()
    if not client or not employee_id:
        return None
    try:
        res = client.table("time_logs").insert({
            "employee_id":   employee_id,
            "employee_name": employee_name,
            "task":          task,
            "date":          date_str,
            "start_time":    start_dt.isoformat(),
            "status":        "RUNNING"
        }).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        print(f"Log start upload error: {e}")
        return None

def upload_log_complete(sb_log_id: str, end_dt, duration_hours: float, break_hours: float): 
    client = sb()
    if not client or not sb_log_id:
        return
    try:
        client.table("time_logs").update({
            "end_time":       end_dt.isoformat(),
            "duration_hours": round(duration_hours, 4),
            "break_hours":    round(break_hours, 4),
            "status":         "COMPLETED"
        }).eq("id", sb_log_id).execute()
    except Exception as e:
        print(f"Log complete upload error: {e}")

def upload_log_interrupted(sb_log_id: str):   
    client = sb()
    if not client or not sb_log_id:
        return
    try:
        client.table("time_logs").update({
            "status": "INTERRUPTED"
        }).eq("id", sb_log_id).execute()
    except Exception as e:
        print(f"Log interrupted upload error: {e}")

def upload_heartbeat(sb_log_id: str, current_duration: float, current_break: float):
   
    client = sb()
    if not client or not sb_log_id:
        return
    try:
        now = datetime.now(ist)
        client.table("time_logs").update({
            "last_heartbeat":      now.isoformat(),
            "duration_hours":      round(current_duration, 4),
            "break_hours":         round(current_break, 4),
        }).eq("id", sb_log_id).execute()
    except Exception as e:
        print(f"Heartbeat error: {e}")

def mark_stale_running_logs():
   
    client = sb()
    if not client:
        return
    try:
        from datetime import timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        client.table("time_logs").update({
            "status": "INTERRUPTED"
        }).eq("status", "RUNNING").lt("last_heartbeat", cutoff).execute()
       
        client.table("time_logs").update({
            "status": "INTERRUPTED"
        }).eq("status", "RUNNING").is_("last_heartbeat", "null").execute()
    except Exception as e:
        print(f"Stale log cleanup error: {e}")


app_data_path = os.getenv('APPDATA', os.path.expanduser("~"))
db_folder     = os.path.join(app_data_path, "WorkClock_Pro")
os.makedirs(db_folder, exist_ok=True)
DB_NAME = os.path.join(db_folder, "workclock.db")

conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c    = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS time_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task           TEXT,
    start_time     REAL,
    end_time       REAL,
    duration       REAL,
    date           TEXT,
    break_duration REAL,
    interrupted    INTEGER DEFAULT 0,
    status         TEXT
)''')

try:
    c.execute("ALTER TABLE time_logs ADD COLUMN last_seen REAL")
    conn.commit()
except Exception:
    pass

c.execute('''CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
)''')
conn.commit()


BG          = "#0F1724"
CARD        = "#1A2535"
CARD2       = "#1E2D40"
ACCENT      = "#3B82F6"
ACCENT_DK   = "#2563EB"
SUCCESS     = "#10B981"
DANGER      = "#EF4444"
WARNING     = "#F59E0B"
TEXT        = "#F1F5F9"
TEXT_MUTED  = "#64748B"
BORDER      = "#2D3F55"
RING_BG     = "#1E3A5F"



def fmt_hms(seconds):
    seconds = max(0, int(seconds))
    h, r   = divmod(seconds, 3600)
    m, s   = divmod(r, 60)
    return f"{h:02}:{m:02}:{s:02}"

def fmt_hm(hours):
    h = int(hours)
    m = int((hours * 60) % 60)
    return f"{h}h {m:02}m"

def get_username():
    c.execute("SELECT value FROM settings WHERE key='username'")
    row = c.fetchone()
    return row[0] if row else None

def set_username(name):
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('username', ?)", (name,))
    conn.commit()
def get_today():
 
    return datetime.now().strftime("%Y-%m-%d")

def get_today_display():
    return datetime.now().strftime("%d-%m-%Y")


def ModernButton(parent, text, command=None, color=ACCENT,
                 text_color=TEXT, width=160, height=42, font_size=10, **kw):

    px = max(10, width // 7)
    py = max(4,  height // 9)

    btn = tk.Label(
        parent,
        text=text,
        font=("Segoe UI", font_size, "bold"),
        fg=text_color,
        bg=color,
        padx=px,
        pady=py,
        cursor="hand2",
        relief="flat",
    )


    btn._mb_color   = color
    btn._mb_hover   = _darken_color(color)
    btn._mb_tc      = text_color
    btn._mb_enabled = True
    btn._mb_command = command

    def _on_enter(e):
        if btn._mb_enabled:
            btn.configure(bg=btn._mb_hover)
    def _on_leave(e):
        if btn._mb_enabled:
            btn.configure(bg=btn._mb_color)
    def _on_press(e):
        if btn._mb_enabled:
            btn.configure(bg=btn._mb_color)
    def _on_release(e):
        if btn._mb_enabled and btn._mb_command:
            btn.configure(bg=btn._mb_hover)
            btn._mb_command()

    btn.bind("<Enter>",           _on_enter)
    btn.bind("<Leave>",           _on_leave)
    btn.bind("<ButtonPress-1>",   _on_press)
    btn.bind("<ButtonRelease-1>", _on_release)

    def set_enabled(enabled):
        btn._mb_enabled = enabled
        col = btn._mb_color if enabled else "#2D3F55"
        tc  = btn._mb_tc    if enabled else TEXT_MUTED
        btn.configure(bg=col, fg=tc, cursor="hand2" if enabled else "arrow")

    def set_text(new_text):
        btn.configure(text=new_text)

    btn.set_enabled = set_enabled
    btn.set_text    = set_text

    return btn


def _darken_color(hex_color):
    r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    r, g, b = max(0,r-30), max(0,g-30), max(0,b-30)
    return f"#{r:02x}{g:02x}{b:02x}"


class RingTimer(tk.Canvas):  
    def __init__(self, parent, size=220, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=parent.cget("bg"), highlightthickness=0, **kw)
        self._size  = size
        self._prog  = 0.0
        self._text  = "00:00:00"
        self._sub   = ""
        self._draw()

    def update_ring(self, elapsed_sec, total_sec, text, sub=""):
        self._prog = min(1.0, elapsed_sec / total_sec) if total_sec > 0 else 0
        self._text = text
        self._sub  = sub
        self._draw()

    def _draw(self):
        self.delete("all")
        s   = self._size
        pad = 14  
        self.create_arc(pad, pad, s-pad, s-pad,
                        start=90, extent=360, style="arc",
                        outline=RING_BG, width=12)
   
        extent = -self._prog * 360
        color  = SUCCESS if self._prog >= 1.0 else ACCENT
        if extent != 0:
            self.create_arc(pad, pad, s-pad, s-pad,
                            start=90, extent=extent, style="arc",
                            outline=color, width=12)
 
        cx, cy = s//2, s//2
        self.create_text(cx, cy-10, text=self._text,
                         fill=TEXT, font=("Segoe UI", 20, "bold"), anchor="center")
        self.create_text(cx, cy+18, text=self._sub,
                         fill=TEXT_MUTED, font=("Segoe UI", 9), anchor="center")


class StatusBadge(tk.Label):
    STATES = {
        "idle":     (TEXT_MUTED, CARD2,    "● IDLE"),
        "tracking": (SUCCESS,    "#0F2918", "● TRACKING"),
        "break":    (WARNING,    "#2D1F00", "● ON BREAK"),
        "stopped":  (DANGER,     "#2D0F0F", "● STOPPED"),
    }
    def __init__(self, parent, **kw):
        super().__init__(parent, font=("Segoe UI", 9, "bold"), padx=12, pady=4, **kw)
        self.set("idle")

    def set(self, state):
        fg, bg, txt = self.STATES.get(state, self.STATES["idle"])
        self.config(text=txt, fg=fg, bg=bg)



class WorkClockPro:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # State
        self.is_tracking    = False
        self.is_on_break    = False
        self.is_locked_out  = False
        self.start_time     = 0.0
        self.break_duration = 0.0
        self.break_start    = 0.0
        self.current_log_id = None
        self.current_date   = get_today()
        self.access_granted = False
        if PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = False

        self._setup_startup()
        self._fix_crashes()
        self.sb_employee_id  = None
        self.sb_log_id       = None
        self._heartbeat_running = False
        def _startup_sb():
            fetch_config_from_supabase()
            mark_stale_running_logs()
        t = threading.Thread(target=_startup_sb, daemon=True)
        t.start()
        t.join(timeout=5)  
        self._build_ui()
        self._tick()


    def _setup_startup(self):
        try:
            exe = os.path.abspath(sys.argv[0])
            if exe.endswith(".exe"):
                sf  = os.path.join(os.getenv("APPDATA",""),
                                   r"Microsoft\Windows\Start Menu\Programs\Startup")
                bat = os.path.join(sf, "WorkClockPro.bat")
                with open(bat, "w") as f:
                    f.write(f'@echo off\nSTART "" "{exe}"')
        except Exception:
            pass

    def _fix_crashes(self):
        c.execute("SELECT id, start_time FROM time_logs WHERE status='RUNNING'")
        for row in c.fetchall():
            c.execute("UPDATE time_logs SET status='INTERRUPTED', end_time=?, duration=0, interrupted=1 WHERE id=?",
                      (row[1], row[0]))
        conn.commit()
      


    def _build_ui(self):        W = 520
        self.root.geometry(f"{W}x700")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)


        header = tk.Frame(self.root, bg=CARD, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="⏱", font=("Segoe UI", 18), bg=CARD, fg=ACCENT).pack(side="left", padx=16)
        tk.Label(header, text=APP_NAME, font=("Segoe UI", 13, "bold"), bg=CARD, fg=TEXT).pack(side="left")
        tk.Label(header, text=APP_VERSION, font=("Segoe UI", 8), bg=CARD, fg=TEXT_MUTED).pack(side="left", padx=6, pady=2, anchor="s")

        self.status_badge = StatusBadge(header)
        self.status_badge.pack(side="right", padx=16)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        body = tk.Frame(self.root, bg=BG)
        body.pack(expand=True, fill="both", padx=24, pady=16)

        self.welcome_card = tk.Frame(body, bg=CARD, padx=20, pady=14)
        self.welcome_card.pack(fill="x", pady=(0,12))
        self._render_welcome()

        # ── Date pill ──
        date_row = tk.Frame(body, bg=BG)
        date_row.pack(fill="x", pady=(0,16))
        today_str = datetime.now().strftime("%A, %d %B %Y") 
        tk.Label(date_row, text=f"📅  {today_str}", font=("Segoe UI", 9),
                 bg=CARD2, fg=TEXT_MUTED, padx=12, pady=6).pack(side="left") 
        ring_frame = tk.Frame(body, bg=BG)
        ring_frame.pack(pady=(0,16))
        self.ring = RingTimer(ring_frame, size=200)
        self.ring.pack()
        prog_card = tk.Frame(body, bg=CARD, padx=20, pady=14)
        prog_card.pack(fill="x", pady=(0,12))

        prog_top = tk.Frame(prog_card, bg=CARD)
        prog_top.pack(fill="x")
        tk.Label(prog_top, text="Daily Target", font=("Segoe UI", 9, "bold"),
                 bg=CARD, fg=TEXT_MUTED).pack(side="left")
        self.lbl_progress = tk.Label(prog_top, text="0h 00m / 9h 00m",
                                     font=("Segoe UI", 9), bg=CARD, fg=TEXT)
        self.lbl_progress.pack(side="right")

        pb_frame = tk.Frame(prog_card, bg=BORDER, height=6)
        pb_frame.pack(fill="x", pady=(8,0))
        self.pb_fill = tk.Frame(pb_frame, bg=ACCENT, height=6)
        self.pb_fill.place(x=0, y=0, relheight=1, relwidth=0)
        self._pb_width = 0
        prog_card.update_idletasks()

        # ── Task input ──
        task_card = tk.Frame(body, bg=CARD, padx=20, pady=14)
        task_card.pack(fill="x", pady=(0,16))

        tk.Label(task_card, text="TASK / PROJECT", font=("Segoe UI", 8, "bold"),
                 bg=CARD, fg=TEXT_MUTED).pack(anchor="w")

        entry_frame = tk.Frame(task_card, bg=BORDER, pady=1)
        entry_frame.pack(fill="x", pady=(6,0))
        inner = tk.Frame(entry_frame, bg=CARD2)
        inner.pack(fill="x", padx=1, pady=1)

        self.task_entry = tk.Entry(inner, font=("Segoe UI", 12), bg=CARD2,
                                   fg=TEXT, insertbackground=TEXT,
                                   relief="flat", bd=8)
        self.task_entry.pack(fill="x")
        self.task_entry.insert(0, "e.g. Dashboard redesign, Bug fixes…")
        self.task_entry.config(fg=TEXT_MUTED)
        self.task_entry.bind("<FocusIn>",  self._clear_placeholder)
        self.task_entry.bind("<FocusOut>", self._restore_placeholder)
        self.task_entry.bind("<Return>",   lambda e: self._start())

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(pady=(0,12))

        self.btn_start = ModernButton(btn_row, "▶  START DAY", command=self._start,
                                      color=SUCCESS, width=148, height=42)
        self.btn_start.grid(row=0, column=0, padx=6)

        self.btn_break = ModernButton(btn_row, "☕  BREAK", command=self._break_toggle,
                                      color=WARNING, width=130, height=42)
        self.btn_break.grid(row=0, column=1, padx=6)
        self.btn_break.set_enabled(False)

        self.btn_stop = ModernButton(btn_row, "■  STOP", command=self._stop,
                                     color=DANGER, width=120, height=42)
        self.btn_stop.grid(row=0, column=2, padx=6)
        self.btn_stop.set_enabled(False)


        bottom = tk.Frame(body, bg=BG)
        bottom.pack(fill="x", pady=(4,0))

        ModernButton(bottom, "📋 View Logs", command=self._view_logs,
                     color=CARD2, text_color=TEXT_MUTED, width=120, height=34, font_size=9
                     ).pack(side="left")
        self.btn_minimize = ModernButton(bottom, "⊟ Minimize", command=self._minimize,
                                         color=CARD2, text_color=TEXT_MUTED,
                                         width=120, height=34, font_size=9)
        self.btn_minimize.pack(side="right")
        self.btn_minimize.set_enabled(False)


    def _render_welcome(self):
        for w in self.welcome_card.winfo_children():
            w.destroy()
        name = get_username()
        if name:
            row = tk.Frame(self.welcome_card, bg=CARD)
            row.pack(fill="x")
            tk.Label(row, text="👋", font=("Segoe UI", 20), bg=CARD).pack(side="left")
            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", padx=10)
            tk.Label(info, text=f"Welcome back,", font=("Segoe UI", 9),
                     bg=CARD, fg=TEXT_MUTED).pack(anchor="w")
            tk.Label(info, text=name, font=("Segoe UI", 14, "bold"),
                     bg=CARD, fg=TEXT).pack(anchor="w")
            ModernButton(row, "Edit", command=self._unlock_edit_name,
                         color=CARD2, text_color=TEXT_MUTED,
                         width=60, height=28, font_size=8).pack(side="right")
        else:
            tk.Label(self.welcome_card, text="ENTER YOUR NAME",
                     font=("Segoe UI", 8, "bold"), bg=CARD, fg=TEXT_MUTED).pack(anchor="w")
            row = tk.Frame(self.welcome_card, bg=CARD)
            row.pack(fill="x", pady=(6,0))
            entry_bg = tk.Frame(row, bg=BORDER, pady=1)
            entry_bg.pack(side="left", expand=True, fill="x", padx=(0,10))
            inner = tk.Frame(entry_bg, bg=CARD2)
            inner.pack(fill="x", padx=1)
            self.name_entry = tk.Entry(inner, font=("Segoe UI", 11), bg=CARD2,
                                       fg=TEXT, insertbackground=TEXT, relief="flat", bd=6)
            self.name_entry.pack(fill="x")
            ModernButton(row, "Save", command=self._save_name,
                         color=ACCENT, width=80, height=34, font_size=9).pack(side="right")

    def _save_name(self):
        name = self.name_entry.get().strip()
        if not name:
            self._flash_error("Name cannot be empty!")
            return
        set_username(name)
        self._render_welcome()

    def _unlock_edit_name(self):
        pwd = simpledialog.askstring(APP_NAME, "Enter password to edit name:", show="*",
                                     parent=self.root)
        if pwd == SECRET_CODE:
            c.execute("DELETE FROM settings WHERE key='username'")
            conn.commit()
            self._render_welcome()
        elif pwd is not None:
            self._flash_error("Wrong password!")


    def _clear_placeholder(self, e):
        if self.task_entry.cget("fg") == TEXT_MUTED:
            self.task_entry.delete(0, "end")
            self.task_entry.config(fg=TEXT)

    def _restore_placeholder(self, e):
        if not self.task_entry.get():
            self.task_entry.insert(0, "e.g. Dashboard redesign, Bug fixes…")
            self.task_entry.config(fg=TEXT_MUTED)

 
    def _get_task(self):
        t = self.task_entry.get().strip()
        if t == "e.g. Dashboard redesign, Bug fixes…":
            return ""
        return t

    def _start(self):
        if self.is_tracking:
            return
        task = self._get_task()
        if not task:
            self._flash_error("Please enter a task name before starting!")
            return

        self.start_time     = time.time()
        self.break_duration = 0.0
        self.is_tracking    = True
        self.task_name      = task

        c.execute('''INSERT INTO time_logs
                     (task,start_time,end_time,duration,date,break_duration,interrupted,status)
                     VALUES (?,?,0,0,?,0,0,'RUNNING')''',
                  (task, self.start_time, self.current_date))
        self.current_log_id = c.lastrowid
        conn.commit()

      
        def _sb_start():
            name = get_username() or "Unknown"
            self.sb_employee_id = ensure_employee_registered(name)
            start_dt = datetime.fromtimestamp(
            self.start_time,
            timezone.utc
            )
            self.sb_log_id = upload_log_start(
                self.sb_employee_id, name, task,
                self.current_date, start_dt
            )
        threading.Thread(target=_sb_start, daemon=True).start()

        self.task_entry.config(state="disabled")
        self.btn_start.set_enabled(False)
        self.btn_break.set_enabled(True)
        self.btn_stop.set_enabled(True)
        self.btn_minimize.set_enabled(True)
        self.status_badge.set("tracking")
   
        self._heartbeat_running = True
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    def _heartbeat_loop(self):
     
        while self._heartbeat_running:
            time.sleep(30)
            if not self._heartbeat_running:
                break
            if self.is_tracking and not self.is_on_break and self.sb_log_id:
                cur_dur = (time.time() - self.start_time - self.break_duration) / 3600
                cur_brk = self.break_duration / 3600
                threading.Thread(
                    target=upload_heartbeat,
                    args=(self.sb_log_id, cur_dur, cur_brk),
                    daemon=True
                ).start()
      
                c.execute("UPDATE time_logs SET last_seen=? WHERE id=?",
                          (time.time(), self.current_log_id))
                conn.commit()

    def _stop(self):
        if not self.is_tracking:
            return
        total_h = self._get_total_hours()
        if total_h < TARGET_HOURS:
            if not self._red_screen(total_h):
                return
        self._finalize(total_h)

    def _finalize(self, total_h):
        self._heartbeat_running = False  
        end_time = time.time()
        dur = round((end_time - self.start_time - self.break_duration) / 3600, 4)
        brk = round(self.break_duration / 3600, 4)
        c.execute('''UPDATE time_logs
                     SET end_time=?, duration=?, break_duration=?, status='COMPLETED'
                     WHERE id=?''',
                  (end_time, dur, self.break_duration, self.current_log_id))
        conn.commit()

 
        _sb_id  = self.sb_log_id
        end_dt = datetime.fromtimestamp(
        end_time,
        timezone.utc
        )
        threading.Thread(
            target=upload_log_complete,
            args=(_sb_id, end_dt, dur, brk),
            daemon=True
        ).start()

        self.is_tracking = False
        self.status_badge.set("stopped")
        self.btn_break.set_enabled(False)
        self.btn_stop.set_enabled(False)

        if total_h >= TARGET_HOURS:
            self._save_timesheet()
            self._show_success_screen()
        else:
 
            messagebox.showinfo(APP_NAME,
                f"Session saved.\n\nWorked: {fmt_hm(total_h)}\nTarget: {fmt_hm(TARGET_HOURS)}",
                parent=self.root)
            self.root.destroy()
            os._exit(0)

    def _get_total_hours(self):
        c.execute("SELECT SUM(duration) FROM time_logs WHERE date=? AND status='COMPLETED'",
                  (self.current_date,))
        row = c.fetchone()
        past = row[0] or 0.0
        cur  = 0.0
        if self.is_tracking:
            cur = (time.time() - self.start_time - self.break_duration) / 3600
        return past + cur

    # ── BREAK ────────────────────────────────
    def _break_toggle(self):
        if not self.is_tracking:
            return
        if self.is_on_break:
            self._end_break()
        else:
            self._start_break()

    def _start_break(self):
        self.break_start  = time.time()
        self.is_on_break  = True
        self.status_badge.set("break")
        self.btn_break.set_text("▶  RESUME")

        self.break_win = tk.Toplevel(self.root)
        self.break_win.title("On Break")
        self.break_win.attributes("-fullscreen", True)
        self.break_win.attributes("-topmost", True)
        self.break_win.overrideredirect(True)
        self.break_win.configure(bg="#0A1628")
        self.break_win.protocol("WM_DELETE_WINDOW", lambda: None)

        cf = tk.Frame(self.break_win, bg="#0A1628")
        cf.pack(expand=True)

        tk.Label(cf, text="☕", font=("Segoe UI", 52), bg="#0A1628").pack(pady=(0,8))
        tk.Label(cf, text="ON BREAK", font=("Segoe UI", 16, "bold"),
                 bg="#0A1628", fg=WARNING).pack()
        tk.Label(cf, text="Take a moment. You earned it.",
                 font=("Segoe UI", 10), bg="#0A1628", fg=TEXT_MUTED).pack(pady=4)

        self.lbl_break_time = tk.Label(cf, text="00:00", font=("Segoe UI", 52, "bold"),
                                       bg="#0A1628", fg=TEXT)
        self.lbl_break_time.pack(pady=20)

        ModernButton(cf, "▶  END BREAK", command=self._end_break,
                     color=SUCCESS, width=180, height=48, font_size=12).pack(pady=10)

        if PYAUTOGUI_AVAILABLE:
            threading.Thread(target=self._trap_mouse_break, daemon=True).start()
        self._tick_break()

    def _end_break(self):
        self.break_duration += time.time() - self.break_start
        self.is_on_break     = False
        self.status_badge.set("tracking")
        self.btn_break.set_text("☕  BREAK")
        try:
            self.break_win.destroy()
        except Exception:
            pass
        # Update break in Supabase
        if self.sb_log_id:
            _brk = self.break_duration / 3600
            _sid = self.sb_log_id
            threading.Thread(
                target=lambda: upload_heartbeat(_sid,
                    (time.time() - self.start_time - self.break_duration) / 3600,
                    _brk),
                daemon=True
            ).start()

    def _tick_break(self):
        if not self.is_on_break:
            return
        elapsed = int(time.time() - self.break_start)
        m, s    = divmod(elapsed, 60)
        try:
            self.lbl_break_time.config(text=f"{m:02}:{s:02}")
            self.break_win.after(1000, self._tick_break)
        except Exception:
            pass

    def _trap_mouse_break(self):
        while self.is_on_break:
            try:
                if self.break_win.winfo_exists():
                    self.break_win.attributes("-topmost", True)
                    x, y = self.break_win.winfo_pointerxy()
                    w, h = self.break_win.winfo_width(), self.break_win.winfo_height()
                    if x < 5 or x > w-5 or y < 5 or y > h-5:
                        pyautogui.moveTo(w//2, h//2)
            except Exception:
                pass
            time.sleep(0.1)

    # ── TICK (main update) ───────────────────
    def _tick(self):
        if self.is_tracking and not self.is_on_break:
            elapsed = time.time() - self.start_time - self.break_duration
            total_target_sec = TARGET_HOURS * 3600
            total_h = self._get_total_hours()
            pct = min(1.0, total_h / TARGET_HOURS)

            # Ring
            sub = f"Goal: {fmt_hm(TARGET_HOURS)} • Break: {fmt_hm(self.break_duration/3600)}"
            self.ring.update_ring(elapsed, total_target_sec, fmt_hms(elapsed), sub)

            # Progress bar
            self.lbl_progress.config(text=f"{fmt_hm(total_h)} / {fmt_hm(TARGET_HOURS)}")
            try:
                bar_w = self.root.winfo_width() - 88  # approx
                self.pb_fill.place(x=0, y=0, relheight=1, width=int(bar_w * pct))
            except Exception:
                pass
        elif not self.is_tracking:
            self.ring.update_ring(0, 1, "00:00:00", "Press START to begin")

        self.root.after(1000, self._tick)

    # ── RED SCREEN ───────────────────────────
    def _red_screen(self, total_h):
        remaining   = TARGET_HOURS - total_h
        self.access_granted = False
        self.is_locked_out  = True

        win = tk.Toplevel(self.root)
        win.attributes("-fullscreen", True)
        win.attributes("-topmost", True)
        win.configure(bg="#1A0000")
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        cf = tk.Frame(win, bg="#1A0000")
        cf.pack(expand=True)

        tk.Label(cf, text="⚠️", font=("Segoe UI", 48), bg="#1A0000").pack()
        tk.Label(cf, text="TARGET NOT MET", font=("Segoe UI", 28, "bold"),
                 bg="#1A0000", fg=DANGER).pack(pady=4)
        tk.Label(cf, text=f"You need {fmt_hm(remaining)} more to hit your daily goal.",
                 font=("Segoe UI", 13), bg="#1A0000", fg=TEXT_MUTED).pack(pady=8)

        # Progress bar inside red screen
        pb_outer = tk.Frame(cf, bg=BORDER, height=8, width=380)
        pb_outer.pack(pady=(4,20))
        pb_outer.pack_propagate(False)
        pct = total_h / TARGET_HOURS
        tk.Frame(pb_outer, bg=DANGER, height=8,
                 width=int(380*pct)).pack(side="left", fill="y")

        tk.Label(cf, text="OVERRIDE PASSWORD", font=("Segoe UI", 9, "bold"),
                 bg="#1A0000", fg=TEXT_MUTED).pack()

        pwd_frame = tk.Frame(cf, bg=BORDER, pady=1, padx=1)
        pwd_frame.pack(pady=(6,16))
        self.red_entry = tk.Entry(pwd_frame, show="●", font=("Segoe UI", 14),
                                  bg="#2D0000", fg=TEXT, insertbackground=TEXT,
                                  relief="flat", bd=10, width=22)
        self.red_entry.pack()
        self.red_entry.focus()

        btn_row = tk.Frame(cf, bg="#1A0000")
        btn_row.pack()

        def verify():
            if self.red_entry.get() == SECRET_CODE:
                self.access_granted = True
                self.is_locked_out  = False
                win.destroy()
            else:
                self.red_entry.delete(0, "end")
                tk.Label(cf, text="✗  Incorrect password",
                         font=("Segoe UI", 9), bg="#1A0000", fg=DANGER).pack(pady=2)

        def go_back():
            self.is_locked_out = False
            win.destroy()

        ModernButton(btn_row, "🔓  Unlock & Exit",  command=verify,
                     color=DANGER, width=160, height=40).pack(side="left", padx=8)
        ModernButton(btn_row, "← Back to Work",  command=go_back,
                     color=CARD2, text_color=TEXT, width=150, height=40).pack(side="left", padx=8)

        win.bind("<Return>", lambda e: verify())

        if PYAUTOGUI_AVAILABLE:
            threading.Thread(target=lambda: self._trap_mouse_win(win), daemon=True).start()

        self.root.wait_window(win)
        return self.access_granted

    def _trap_mouse_win(self, win):
        while self.is_locked_out:
            try:
                if win.winfo_exists():
                    win.attributes("-topmost", True)
                    x, y = win.winfo_pointerxy()
                    w, h = win.winfo_width(), win.winfo_height()
                    if x < 5 or x > w-5 or y < 5 or y > h-5:
                        pyautogui.moveTo(w//2, h//2)
            except Exception:
                pass
            time.sleep(0.1)


    def _show_success_screen(self):
        win = tk.Toplevel(self.root)
        win.attributes("-fullscreen", True)
        win.configure(bg="#0A2010")
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        cf = tk.Frame(win, bg="#0A2010")
        cf.pack(expand=True)

        tk.Label(cf, text="🎯", font=("Segoe UI", 56), bg="#0A2010").pack()
        tk.Label(cf, text="TARGET ACHIEVED!", font=("Segoe UI", 32, "bold"),
                 bg="#0A2010", fg=SUCCESS).pack(pady=8)
        total_h = self._get_total_hours()
        tk.Label(cf, text=f"You worked {fmt_hm(total_h)} today. Great job!",
                 font=("Segoe UI", 13), bg="#0A2010", fg=TEXT_MUTED).pack(pady=4)
        tk.Label(cf, text="Your timesheet has been saved.",
                 font=("Segoe UI", 10), bg="#0A2010", fg=TEXT_MUTED).pack(pady=2)

        ModernButton(cf, "Exit App", command=self._hard_exit,
                     color=SUCCESS, width=160, height=46, font_size=12).pack(pady=24)

  
    def _view_logs(self):
        win = tk.Toplevel(self.root)
        win.title(f"Logs — {get_today_display()}")
        win.geometry("860x420")
        win.configure(bg=BG)

        tk.Label(win, text=f"Work Logs  ·  {get_today_display()}",
                 font=("Segoe UI", 12, "bold"), bg=BG, fg=TEXT,
                 padx=20, pady=12).pack(anchor="w")
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x")

        style = ttk.Style(win)
        style.theme_use("clam")
        style.configure("Logs.Treeview",
                        background=CARD, foreground=TEXT,
                        rowheight=30, fieldbackground=CARD,
                        borderwidth=0, font=("Segoe UI", 9))
        style.configure("Logs.Treeview.Heading",
                        background=CARD2, foreground=TEXT_MUTED,
                        font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Logs.Treeview", background=[("selected", ACCENT_DK)])

        cols = ("Task", "Started", "Break", "Finished", "Hours", "Status")
        tree = ttk.Treeview(win, columns=cols, show="headings", style="Logs.Treeview")
        widths = [200, 90, 80, 90, 80, 140]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center" if col != "Task" else "w")
        tree.pack(fill="both", expand=True, padx=16, pady=12)

        c.execute("SELECT * FROM time_logs WHERE date=? ORDER BY id DESC",
                  (self.current_date,))
        for row in c.fetchall():
            st  = datetime.fromtimestamp(row[2]).strftime("%H:%M:%S")
            brk = f"{int(row[6]//60)}m {int(row[6]%60)}s"
            st8 = row[8]
            et  = "Active…"        if st8 == "RUNNING" else \
                  "Unknown"        if st8 == "INTERRUPTED" else \
                  datetime.fromtimestamp(row[3]).strftime("%H:%M:%S")
            dur = "Counting…"      if st8 == "RUNNING" else \
                  "—"              if st8 == "INTERRUPTED" else \
                  f"{row[4]:.2f}h"
            tree.insert("", "end", values=(row[1], st, brk, et, dur, st8))

    def _minimize(self):
        if not TRAY_AVAILABLE:
            self.root.iconify()
            return
        self.root.withdraw()
        icon = Image.new("RGB", (64,64), color="#3B82F6")
        self.tray = pystray.Icon(APP_NAME, icon,
                                 menu=pystray.Menu(item("Restore", self._restore)))
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _restore(self):
        if hasattr(self, "tray"):
            self.tray.stop()
        self.root.deiconify()

  
    def _flash_error(self, msg):
        messagebox.showerror(APP_NAME, msg, parent=self.root)

    def _save_timesheet(self):
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        path = os.path.join(docs, f"WorkClock_Timesheet_{get_today_display()}.txt")
        name = get_username() or "Unknown"
        c.execute("SELECT task, duration, break_duration FROM time_logs WHERE date=? AND status='COMPLETED'",
                  (self.current_date,))
        rows = c.fetchall()
        with open(path, "w") as f:
            f.write(f"{APP_NAME} — Daily Timesheet\n")
            f.write(f"Date: {get_today_display()}   Employee: {name}\n")
            f.write("─" * 50 + "\n")
            total = 0
            for r in rows:
                f.write(f"Task: {r[0]}\n")
                f.write(f"  Duration : {r[1]:.2f}h\n")
                f.write(f"  Break    : {fmt_hm(r[2]/3600)}\n")
                total += r[1]
            f.write("─" * 50 + "\n")
            f.write(f"TOTAL HOURS: {total:.2f}h\n")
        try:
            os.startfile(path)
        except Exception:
            pass

    def _on_close(self):
        if self.is_tracking:
            if not self._red_screen(self._get_total_hours()):
                return
        self._heartbeat_running = False
        self._hard_exit()

    def _hard_exit(self):
        self.root.destroy()
        os._exit(0)



if __name__ == "__main__":
    root = tk.Tk()
    app  = WorkClockPro(root)
    root.mainloop()