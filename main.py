import flet as ft
import threading
import subprocess
import sys
import os
import socket
import time

_server_process = None

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run_fastapi():
    global _server_process
    script_dir = os.path.dirname(os.path.abspath(__file__))
    _server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app",
         "--host", "0.0.0.0", "--port", "8000", "--log-level", "error"],
        cwd=script_dir
    )

def main(page: ft.Page):
    page.title = "CinePix Background Server"
    page.theme_mode = ft.ThemeMode.DARK
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.bgcolor = "#0f172a"
    page.padding = 30

    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()
    time.sleep(1.5)

    local_ip = get_local_ip()

    title = ft.Text("CinePix Server", size=32, weight=ft.FontWeight.BOLD, color="#38bdf8")
    status_icon = ft.Icon(name=ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_500, size=60)
    status_text = ft.Text("Server is Running", size=20, color=ft.colors.GREEN_400)

    ip_info = ft.Container(
        content=ft.Column([
            ft.Text("API running at:", color="#94a3b8", size=14),
            ft.Text(f"http://127.0.0.1:8000", size=18, weight=ft.FontWeight.BOLD, color="#f8fafc", selectable=True),
            ft.Text(f"Network: http://{local_ip}:8000", size=14, color="#64748b", selectable=True),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=20,
        bgcolor="#1e293b",
        border_radius=10,
        margin=ft.margin.only(top=20, bottom=20)
    )

    monitor_btn = ft.ElevatedButton(
        text="Open Monitor Dashboard",
        icon=ft.icons.MONITOR_HEART,
        color=ft.colors.WHITE,
        bgcolor="#0284c7",
        on_click=lambda _: page.launch_url("http://127.0.0.1:8000/monitor")
    )

    instructions = ft.Text(
        "Minimize this app. The scraping server will keep running in background.",
        text_align=ft.TextAlign.CENTER,
        color="#94a3b8",
        size=13
    )

    page.add(ft.Column(
        [title, ft.Container(height=20), status_icon, status_text,
         ip_info, monitor_btn, ft.Container(height=20), instructions],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER
    ))

ft.app(target=main)
