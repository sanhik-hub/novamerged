import os
import sys
import time
import socket
import threading
import subprocess
import webbrowser
import tempfile
import tkinter as tk
from tkinter import messagebox
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 5000
CLIENT_PORT = 5173
ADMIN_PORT = 5174


def get_root():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent

    exe_dir = Path(sys.executable).resolve().parent

    # Final installed layout:
    #
    # PrismAI/
    #   PrismLauncher.exe
    #   client/
    #   admin/
    #   server/
    #   assets/
    #
    if (
        (exe_dir / "client").exists()
        or (exe_dir / "admin").exists()
        or (exe_dir / "server").exists()
    ):
        return exe_dir

    # Development packaged layout:
    #
    # Computational_Thinking_2025-26/
    #   dist/
    #       PrismLauncher.exe
    #       PrismAi/
    #
    if (exe_dir / "PrismAi" / "PrismAi.exe").exists():
        return exe_dir.parent

    return exe_dir


ROOT = get_root()


def show_error(title, message):
    try:
        messagebox.showerror(title, message)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                message,
                title,
                0x10,
            )
        except Exception:
            pass


def port_is_open(host, port):
    try:
        with socket.create_connection(
            (host, port),
            timeout=0.5,
        ):
            return True
    except OSError:
        return False


def wait_for_backend(timeout=60, stop_event=None):
    deadline = time.monotonic() + timeout
    stop_event = stop_event or threading.Event()

    while time.monotonic() < deadline:
        if stop_event.is_set():
            return False

        if port_is_open(
            BACKEND_HOST,
            BACKEND_PORT,
        ):
            return True

        # Wait without time.sleep().
        # The event allows shutdown to interrupt this wait immediately.
        remaining = max(
            0.0,
            min(0.25, deadline - time.monotonic()),
        )

        if stop_event.wait(remaining):
            return False

    return port_is_open(
        BACKEND_HOST,
        BACKEND_PORT,
    )


def find_backend():
    candidates = [
        ROOT / "server" / "PrismAi.exe",
        ROOT / "dist" / "PrismAi" / "PrismAi.exe",
    ]

    for path in candidates:
        if path.exists():
            return path

    searched = "\n".join(
        str(path)
        for path in candidates
    )

    raise FileNotFoundError(
        "The computational backend was not found.\n\n"
        f"Searched:\n{searched}"
    )


def get_backend_log_path():
    log_root = Path(
        os.environ.get(
            "LOCALAPPDATA",
            str(Path.home() / "AppData" / "Local"),
        )
    ) / "PrismAI" / "logs"

    log_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    return log_root / "backend.log"


def start_backend(stop_event=None):
    """
    Start the computational backend as an independent process.

    The backend is deliberately NOT treated as a child service that
    belongs to the Control Center lifecycle. The launcher may start
    it when port 5000 is unavailable, but the backend remains alive
    independently if the Control Center closes.

    Backend stdout/stderr are persisted so startup failures are
    diagnosable even when PrismLauncher is started from Explorer.
    """
    backend_exe = find_backend()
    backend_dir = backend_exe.parent
    stop_event = stop_event or threading.Event()

    # Reuse an already-running backend.
    if port_is_open(
        BACKEND_HOST,
        BACKEND_PORT,
    ):
        return None

    if stop_event.is_set():
        return None

    log_path = get_backend_log_path()

    try:
        log_file = open(
            log_path,
            "a",
            encoding="utf-8",
            buffering=1,
        )
    except Exception:
        log_file = open(
            os.devnull,
            "w",
            encoding="utf-8",
        )

    try:
        import datetime

        log_file.write(
            "\n"
            + "=" * 72
            + "\n"
            + f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] "
              "PrismAI backend launch requested\n"
            + f"Executable: {backend_exe}\n"
            + f"Working directory: {backend_dir}\n"
            + "=" * 72
            + "\n"
        )
        log_file.flush()

        creation_flags = 0

        if os.name == "nt":
            creation_flags = (
                subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
            )

        process = subprocess.Popen(
            [str(backend_exe)],
            cwd=str(backend_dir),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
            close_fds=True,
        )

        # The backend owns its own lifetime. The launcher only uses
        # this Popen object to observe startup while it is launching.
        # Do not tie backend startup to the Control Center's
        # shutdown event. The backend is detached and its
        # lifetime is controlled explicitly by close_prism().
        ready = wait_for_backend(60)

        if not ready:
            try:
                return_code = process.poll()
            except Exception:
                return_code = None

            log_file.write(
                f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] "
                f"Backend did not become ready. "
                f"Return code: {return_code}\n"
            )
            log_file.flush()

            # Only terminate a process that we just created and only
            # when startup actually failed. This is NOT normal launcher
            # shutdown logic.
            terminate_process_tree(process)

            if stop_event.is_set():
                return None

            raise RuntimeError(
                "The computational backend did not become ready "
                "within 60 seconds.\n\n"
                f"Backend log:\n{log_path}"
            )

        log_file.write(
            f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] "
            "Backend is listening on "
            f"{BACKEND_HOST}:{BACKEND_PORT}\n"
        )
        log_file.flush()

        # Do not retain the log file as a live handle in the launcher.
        # The backend has its own process lifetime.
        try:
            log_file.close()
        except Exception:
            pass

        return process

    except Exception:
        try:
            log_file.close()
        except Exception:
            pass
        raise


def terminate_process_tree(process):
    """Terminate a Windows process and all of its children."""
    if process is None:
        return

    try:
        if process.poll() is not None:
            return
    except Exception:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return
        except Exception:
            pass

    try:
        process.terminate()
    except Exception:
        pass


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def find_available_port(preferred_port):
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        try:
            sock.bind(
                (BACKEND_HOST, preferred_port)
            )
            return preferred_port
        except OSError:
            pass

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.bind(
            (BACKEND_HOST, 0)
        )

        return sock.getsockname()[1]


def find_frontend(admin_mode):
    if getattr(sys, "frozen", False):
        if admin_mode:
            candidates = [
                ROOT / "admin",
                ROOT / "Admin" / "dist",
                ROOT / "Admin",
            ]
        else:
            candidates = [
                ROOT / "client",
                ROOT / "client" / "dist",
            ]
    else:
        if admin_mode:
            candidates = [
                ROOT / "Admin" / "dist",
                ROOT / "Admin",
            ]
        else:
            candidates = [
                ROOT / "client" / "dist",
                ROOT / "client",
            ]

    for directory in candidates:
        if (
            directory.exists()
            and (directory / "index.html").exists()
        ):
            return directory

    searched = "\n".join(
        str(path)
        for path in candidates
    )

    raise FileNotFoundError(
        "The frontend build was not found.\n\n"
        f"Searched:\n{searched}"
    )

def start_static_server(
    directory,
    preferred_port,
):
    directory = Path(directory).resolve()

    if not directory.exists():
        raise FileNotFoundError(
            "Frontend build directory was not found:\n\n"
            f"{directory}"
        )

    if not (
        directory / "index.html"
    ).exists():
        raise FileNotFoundError(
            "Frontend index.html was not found:\n\n"
            f"{directory / 'index.html'}"
        )

    port = find_available_port(
        preferred_port
    )

    def handler(*args, **kwargs):
        return QuietHandler(
            *args,
            directory=str(directory),
            **kwargs,
        )

    server = ThreadingHTTPServer(
        (
            BACKEND_HOST,
            port,
        ),
        handler,
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )

    thread.start()

    return server, port


class PrismControlCenter:
    def __init__(self, root):
        self.root = root

        self.root.title("PrismAI Control Center")
        self.root.geometry("780x780")
        self.root.minsize(740, 720)
        self.root.protocol("WM_DELETE_WINDOW", self.close_prism)

        # Backend lifecycle is independent from the Control Center.
        # This reference is used only to observe startup.
        self.backend_process = None
        self.backend_started_by_prism = False

        self.client_server = None
        self.client_port = None

        self.admin_server = None
        self.admin_port = None

        self.client_browser_process = None
        self.admin_browser_process = None

        self.browser_profile_root = Path(
            tempfile.mkdtemp(prefix="PrismAI-Browser-")
        )

        self.closing = False
        self.shutdown_event = threading.Event()

        self._set_icon()

        self.build_ui()

        self.set_status(
            self.backend_status,
            "Starting..."
        )

        self.set_status(
            self.client_status,
            "Stopped"
        )

        self.set_status(
            self.admin_status,
            "Stopped"
        )

        self.start_backend_async()

        self.refresh_status()

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _set_icon(self):
        candidates = [
            ROOT / "assets" / "prism.ico",
            ROOT / "prism.ico",
        ]

        for icon in candidates:
            if icon.exists():
                try:
                    self.root.iconbitmap(str(icon))
                except Exception:
                    pass
                break

    def build_ui(self):
        # ----------------------------------------------------
        # Black / purple theme
        # ----------------------------------------------------

        BG = "#0b0710"
        PANEL = "#130d1c"
        PANEL_2 = "#1a1024"
        PURPLE = "#8b5cf6"
        PURPLE_DARK = "#6d28d9"
        PURPLE_LIGHT = "#a78bfa"
        TEXT = "#f5f3ff"
        MUTED = "#aaa0b8"
        BORDER = "#30213d"
        SUCCESS = "#8ee6a8"
        WARNING = "#f5c86c"

        self.COLORS = {
            "bg": BG,
            "panel": PANEL,
            "panel2": PANEL_2,
            "purple": PURPLE,
            "purple_dark": PURPLE_DARK,
            "purple_light": PURPLE_LIGHT,
            "text": TEXT,
            "muted": MUTED,
            "border": BORDER,
            "success": SUCCESS,
            "warning": WARNING,
        }

        self.root.configure(
            bg=BG,
        )

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = tk.Frame(
            self.root,
            bg=BG,
        )
        header.pack(
            fill="x",
            padx=28,
            pady=(24, 12),
        )

        tk.Label(
            header,
            text="PrismAI",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 24, "bold"),
        ).pack(
            anchor="w",
        )

        tk.Label(
            header,
            text="Control Center",
            bg=BG,
            fg=PURPLE_LIGHT,
            font=("Segoe UI", 11),
        ).pack(
            anchor="w",
            pady=(0, 2),
        )

        tk.Label(
            header,
            text="Manage your local Prism services",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(
            anchor="w",
        )

        # ----------------------------------------------------
        # Services
        # ----------------------------------------------------

        self.services_frame = tk.Frame(
            self.root,
            bg=BG,
        )
        self.services_frame.pack(
            fill="x",
            padx=28,
        )

        self.backend_status = self.add_service(
            self.services_frame,
            "Backend",
            BACKEND_PORT,
            "backend",
        )

        self.client_status = self.add_service(
            self.services_frame,
            "Prism",
            CLIENT_PORT,
            "client",
        )

        self.admin_status = self.add_service(
            self.services_frame,
            "Admin",
            ADMIN_PORT,
            "admin",
        )

        # ----------------------------------------------------
        # Controls
        # ----------------------------------------------------

        controls = tk.Frame(
            self.root,
            bg=BG,
        )
        controls.pack(
            fill="x",
            padx=28,
            pady=(18, 10),
        )

        # Prism row
        prism_row = tk.Frame(
            controls,
            bg=BG,
        )
        prism_row.pack(
            fill="x",
            pady=4,
        )

        tk.Label(
            prism_row,
            text="PRISM",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
            width=10,
            anchor="w",
        ).pack(
            side="left",
        )

        tk.Button(
            prism_row,
            text="Open Prism",
            bg=PURPLE,
            fg="white",
            activebackground=PURPLE_LIGHT,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=18,
            pady=9,
            cursor="hand2",
            command=self.open_prism,
        ).pack(
            side="left",
            padx=(0, 8),
        )

        tk.Button(
            prism_row,
            text="Terminate Prism",
            bg=PANEL_2,
            fg=TEXT,
            activebackground=PURPLE_DARK,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=18,
            pady=9,
            cursor="hand2",
            command=self.terminate_prism,
        ).pack(
            side="left",
        )

        # Admin row
        admin_row = tk.Frame(
            controls,
            bg=BG,
        )
        admin_row.pack(
            fill="x",
            pady=4,
        )

        tk.Label(
            admin_row,
            text="ADMIN",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
            width=10,
            anchor="w",
        ).pack(
            side="left",
        )

        tk.Button(
            admin_row,
            text="Open Admin",
            bg=PURPLE_DARK,
            fg="white",
            activebackground=PURPLE,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=18,
            pady=9,
            cursor="hand2",
            command=self.open_admin,
        ).pack(
            side="left",
            padx=(0, 8),
        )

        tk.Button(
            admin_row,
            text="Terminate Admin",
            bg=PANEL_2,
            fg=TEXT,
            activebackground=PURPLE_DARK,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=18,
            pady=9,
            cursor="hand2",
            command=self.terminate_admin,
        ).pack(
            side="left",
        )

        # ----------------------------------------------------
        # Event console
        # ----------------------------------------------------

        console_frame = tk.Frame(
            self.root,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        console_frame.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=(8, 10),
        )

        console_header = tk.Frame(
            console_frame,
            bg=PANEL,
        )
        console_header.pack(
            fill="x",
            padx=12,
            pady=(8, 2),
        )

        tk.Label(
            console_header,
            text="Activity",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(
            side="left",
        )

        self.console = tk.Text(
            console_frame,
            height=5,
            bg="#09060d",
            fg=MUTED,
            insertbackground=PURPLE_LIGHT,
            relief="flat",
            bd=0,
            font=("Consolas", 8),
            wrap="word",
            state="disabled",
            padx=10,
            pady=6,
        )
        self.console.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=(2, 8),
        )

        # ----------------------------------------------------
        # Master close
        # ----------------------------------------------------

        close_frame = tk.Frame(
            self.root,
            bg=BG,
        )
        close_frame.pack(
            fill="x",
            padx=28,
            pady=(0, 22),
        )

        tk.Button(
            close_frame,
            text="CLOSE PRISM",
            bg="#25102e",
            fg="#f1d9ff",
            activebackground="#4c1d5f",
            activeforeground="white",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            pady=10,
            cursor="hand2",
            command=self.close_prism,
        ).pack(
            fill="x",
        )

        self.log_event("Control Center started.")

    def add_service(
        self,
        parent,
        name,
        preferred_port,
        service_type,
    ):
        colors = getattr(
            self,
            "COLORS",
            {
                "panel": "#130d1c",
                "panel2": "#1a1024",
                "border": "#30213d",
                "text": "#f5f3ff",
                "muted": "#aaa0b8",
            },
        )

        frame = tk.Frame(
            parent,
            bg=colors["panel"],
            highlightbackground=colors["border"],
            highlightthickness=1,
            padx=14,
            pady=9,
        )
        frame.pack(
            fill="x",
            pady=4,
        )

        left = tk.Frame(
            frame,
            bg=colors["panel"],
        )
        left.pack(
            side="left",
            fill="x",
            expand=True,
        )

        tk.Label(
            left,
            text=name,
            bg=colors["panel"],
            fg=colors["text"],
            font=("Segoe UI", 10, "bold"),
        ).pack(
            anchor="w",
        )

        tk.Label(
            left,
            text=f"127.0.0.1:{preferred_port}",
            bg=colors["panel"],
            fg=colors["muted"],
            font=("Consolas", 8),
        ).pack(
            anchor="w",
            pady=(1, 0),
        )

        status = tk.Label(
            frame,
            text="Stopped",
            bg=colors["panel"],
            fg=colors["muted"],
            font=("Segoe UI", 9, "bold"),
            width=25,
            anchor="e",
        )
        status.pack(
            side="right",
        )

        return {
            "label": status,
            "name": name,
            "preferred_port": preferred_port,
            "service_type": service_type,
        }

    def log_event(self, message):
        try:
            import datetime

            timestamp = datetime.datetime.now().strftime(
                "%H:%M:%S"
            )

            self.console.configure(
                state="normal"
            )

            self.console.insert(
                "end",
                f"[{timestamp}] {message}\n",
            )

            self.console.see("end")

            self.console.configure(
                state="disabled"
            )
        except Exception:
            pass

    def set_status(self, item, text):
        try:
            item["label"].configure(
                text=text
            )
        except Exception:
            pass

    def set_message(self, text):
        try:
            self.message_label.configure(
                text=text
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # Backend
    # --------------------------------------------------------

    def start_backend_async(self):
        thread = threading.Thread(
            target=self._start_backend_worker,
            daemon=True,
        )
        thread.start()

    def _start_backend_worker(self):
        try:
            process = start_backend(
                stop_event=self.shutdown_event,
            )

            self.backend_process = process
            self.backend_started_by_prism = process is not None

            if self.closing:
                return

            self.safe_after(
                0,
                lambda: self.set_message(
                    "Backend is ready."
                ),
            )

            self.safe_after(
                0,
                lambda: self.log_event(
                    "Backend started on port 5000."
                ),
            )

        except Exception as exc:
            self.safe_after(
                0,
                lambda: self.show_error(
                    "PrismAI",
                    "The computational backend could not be started.\n\n"
                    f"{exc}\n\n"
                    f"Startup diagnostics are available at:\n"
                    f"{get_backend_log_path()}",
                ),
            )

    # --------------------------------------------------------
    # Prism
    # --------------------------------------------------------

    def open_prism(self):
        if self.closing:
            return

        if self.client_server is not None:
            if self.client_server[0].fileno() >= 0:
                self.open_url(
                    self.client_port
                )
                return

        try:
            frontend_dir = find_frontend(False)

            self.client_server, self.client_port = (
                start_static_server(
                    frontend_dir,
                    CLIENT_PORT,
                )
            )

            self.open_url(
                self.client_port,
                "client",
            )

            self.set_message(
                f"Prism running on port {self.client_port}."
            )
            self.log_event(
                f"Prism started on port {self.client_port}."
            )

        except Exception as exc:
            self.show_error(
                "PrismAI",
                f"Prism could not be started.\n\n{exc}",
            )

    def terminate_prism(self):
        if self.client_server is None:
            self.set_message(
                "Prism is already stopped."
            )
            return

        try:
            server = self.client_server[0]

            server.shutdown()
            server.server_close()

        except Exception:
            pass

        self.client_server = None
        self.client_port = None

        self.close_browser("client")

        self.set_message(
            "Prism has been terminated."
        )
        self.log_event(
            "Prism terminated."
        )

    # --------------------------------------------------------
    # Admin
    # --------------------------------------------------------

    def open_admin(self):
        if self.closing:
            return

        if self.admin_server is not None:
            try:
                self.open_url(
                    self.admin_port
                )
                return
            except Exception:
                pass

        try:
            frontend_dir = find_frontend(True)

            self.admin_server, self.admin_port = (
                start_static_server(
                    frontend_dir,
                    ADMIN_PORT,
                )
            )

            self.open_url(
                self.admin_port,
                "admin",
            )

            self.set_message(
                f"Admin running on port {self.admin_port}."
            )
            self.log_event(
                f"Admin started on port {self.admin_port}."
            )

        except Exception as exc:
            self.show_error(
                "PrismAI",
                f"Admin could not be started.\n\n{exc}",
            )

    def terminate_admin(self):
        if self.admin_server is None:
            self.set_message(
                "Admin is already stopped."
            )
            return

        try:
            server = self.admin_server[0]

            server.shutdown()
            server.server_close()

        except Exception:
            pass

        self.admin_server = None
        self.admin_port = None

        self.close_browser("admin")

        self.set_message(
            "Admin has been terminated."
        )
        self.log_event(
            "Admin terminated."
        )

    # --------------------------------------------------------
    # Browser / status
    # --------------------------------------------------------

    def find_browser(self):
        candidates = [
            os.environ.get("LOCALAPPDATA", "") + r"\Google\Chrome\Application\chrome.exe",
            os.environ.get("PROGRAMFILES", "") + r"\Google\Chrome\Application\chrome.exe",
            os.environ.get("PROGRAMFILES(X86)", "") + r"\Google\Chrome\Application\chrome.exe",
            os.environ.get("PROGRAMFILES", "") + r"\Microsoft\Edge\Application\msedge.exe",
            os.environ.get("PROGRAMFILES(X86)", "") + r"\Microsoft\Edge\Application\msedge.exe",
        ]

        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return Path(candidate)

        return None

    def open_url(self, port, service="client"):
        url = (
            f"http://{BACKEND_HOST}:{port}/"
        )

        browser = self.find_browser()

        if browser is None:
            webbrowser.open(url)

            self.log_event(
                f"{service.title()} opened in the default browser."
            )
            return

        profile = (
            self.browser_profile_root
            / service
        )

        profile.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            process = subprocess.Popen(
                [
                    str(browser),
                    f"--user-data-dir={profile}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--new-window",
                    url,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt"
                    else 0
                ),
            )

            if service == "client":
                self.client_browser_process = process
            else:
                self.admin_browser_process = process

            self.log_event(
                f"{service.title()} opened."
            )

        except Exception:
            webbrowser.open(url)

            self.log_event(
                f"{service.title()} opened in the default browser."
            )

    def close_browser(self, service):
        if service == "client":
            process = self.client_browser_process
            self.client_browser_process = None
        else:
            process = self.admin_browser_process
            self.admin_browser_process = None

        if process is None:
            return

        terminate_process_tree(process)

    def refresh_status(self):
        if self.closing:
            return

        # Backend
        # Always verify the actual backend port. The port is the
        # source of truth for the displayed backend status.
        backend_running = port_is_open(
            BACKEND_HOST,
            BACKEND_PORT,
        )

        if backend_running:
            self.set_status(
                self.backend_status,
                f"Running : {BACKEND_HOST}:{BACKEND_PORT}",
            )
        else:
            if self.backend_process is not None:
                try:
                    if self.backend_process.poll() is not None:
                        self.backend_process = None
                except Exception:
                    self.backend_process = None

            self.set_status(
                self.backend_status,
                "Stopped",
            )
        # Prism
        if self.client_server is not None:
            self.set_status(
                self.client_status,
                f"Running : {self.client_port}",
            )
        else:
            self.set_status(
                self.client_status,
                "Stopped",
            )

        # Admin
        if self.admin_server is not None:
            self.set_status(
                self.admin_status,
                f"Running : {self.admin_port}",
            )
        else:
            self.set_status(
                self.admin_status,
                "Stopped",
            )

        try:
            self.root.after(
                1000,
                self.refresh_status,
            )
        except Exception:
            pass

    def safe_after(self, delay, callback):
        if self.closing:
            return

        try:
            self.root.after(
                delay,
                callback,
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    def close_prism(self):
        if self.closing:
            return

        self.closing = True
        self.shutdown_event.set()

        self.set_message(
            "Closing Prism..."
        )

        self.log_event(
            "Closing Prism..."
        )

        self.close_browser("client")
        self.close_browser("admin")

        # Stop main frontend
        if self.client_server is not None:
            try:
                server = self.client_server[0]
                server.shutdown()
                server.server_close()
            except Exception:
                pass

            self.client_server = None
            self.client_port = None

        # Stop Admin
        if self.admin_server is not None:
            try:
                server = self.admin_server[0]
                server.shutdown()
                server.server_close()
            except Exception:
                pass

            self.admin_server = None
            self.admin_port = None

        # -----------------------------------------------------
        # Stop the computational backend if THIS Control Center
        # started it.
        #
        # PrismAi.exe is launched as a detached process so that
        # Windows does not terminate it merely because the
        # Control Center process exits.
        #
        # However, an intentional "CLOSE PRISM" explicitly ends
        # the Prism session, including the backend started by it.
        # -----------------------------------------------------
        if self.backend_started_by_prism and self.backend_process is not None:
            try:
                if self.backend_process.poll() is None:
                    terminate_process_tree(self.backend_process)
            except Exception:
                pass

        self.backend_process = None
        self.backend_started_by_prism = False

        try:
            self.root.destroy()
        except Exception:
            pass

    def show_error(self, title, message):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                message,
                title,
                0x10,
            )
        except Exception:
            pass


def main():
    # Always establish the application root as the working directory.
    # This makes Explorer / Start Menu launches behave consistently
    # with terminal launches.
    try:
        os.chdir(ROOT)
    except Exception:
        pass

    admin_mode = (
        len(sys.argv) > 1
        and sys.argv[1].lower() == "--admin"
    )

    try:
        root = tk.Tk()

        app = PrismControlCenter(root)

        if admin_mode:
            app.open_admin()

        root.mainloop()

    except Exception as exc:
        show_error(
            "PrismAI",
            f"Prism could not be started.\n\n{exc}",
        )


if __name__ == "__main__":
    main()




