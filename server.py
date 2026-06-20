import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import socket
import threading
import json
import os
import base64
import time
import struct
from datetime import datetime

# ─── Configurações ────────────────────────────────────────────────────────────
TCP_PORT = 54321
UDP_PORT = 54322
BROADCAST_INTERVAL = 2  # segundos entre broadcasts UDP
BUFFER_SIZE = 65536
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# ─── Cores e estilo ───────────────────────────────────────────────────────────
BG_DARK     = "#1a1d27"
BG_PANEL    = "#22263a"
BG_CARD     = "#2a2f47"
BG_INPUT    = "#1e2235"
ACCENT      = "#4f8ef7"
ACCENT2     = "#7c5cbf"
GREEN       = "#3ecf8e"
RED         = "#f05f5f"
YELLOW      = "#f5c842"
TEXT_MAIN   = "#e8eaf6"
TEXT_DIM    = "#7b82a8"
TEXT_LINK   = "#6ec6ff"
FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 13, "bold")
FONT_SMALL  = ("Segoe UI", 9)
FONT_MONO   = ("Consolas", 9)


def now_str():
    return datetime.now().strftime("%H:%M")


class ServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LAN Chat — Servidor (Professor)")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("900x650")
        self.root.minsize(750, 500)

        self.clients = {}          # addr -> {"conn": ..., "name": ..., "addr": ...}
        self.history = []          # lista de mensagens para replay em novos clientes
        self.running = False
        self.server_sock = None
        self.udp_sock = None
        self._lock = threading.Lock()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────── UI ──────────────────────────────────────────

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG_DARK)
        header.pack(fill="x", padx=18, pady=(14, 0))

        tk.Label(header, text="◈ LAN Chat", font=("Segoe UI", 16, "bold"),
                 bg=BG_DARK, fg=ACCENT).pack(side="left")
        tk.Label(header, text="  Painel do Professor", font=FONT_MAIN,
                 bg=BG_DARK, fg=TEXT_DIM).pack(side="left")

        self.status_dot = tk.Label(header, text="●", font=("Segoe UI", 14),
                                   bg=BG_DARK, fg=RED)
        self.status_dot.pack(side="right", padx=(0, 4))
        self.status_lbl = tk.Label(header, text="Servidor desligado",
                                   font=FONT_SMALL, bg=BG_DARK, fg=TEXT_DIM)
        self.status_lbl.pack(side="right")

        sep = tk.Frame(self.root, bg=BG_CARD, height=1)
        sep.pack(fill="x", padx=18, pady=(10, 0))

        body = tk.Frame(self.root, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=18, pady=10)

        left = tk.Frame(body, bg=BG_DARK)
        left.pack(side="left", fill="both", expand=True)

        self._build_chat(left)

        right = tk.Frame(body, bg=BG_DARK, width=220)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        self._build_sidebar(right)

    def _build_chat(self, parent):
        lbl = tk.Label(parent, text="Histórico da Aula", font=FONT_BOLD,
                       bg=BG_DARK, fg=TEXT_DIM)
        lbl.pack(anchor="w", pady=(0, 4))

        frame = tk.Frame(parent, bg=BG_CARD, bd=0)
        frame.pack(fill="both", expand=True)

        self.chat_area = scrolledtext.ScrolledText(
            frame, state="disabled", wrap="word",
            bg=BG_CARD, fg=TEXT_MAIN, font=FONT_MAIN,
            bd=0, padx=10, pady=8,
            selectbackground=ACCENT, cursor="arrow",
            insertbackground=TEXT_MAIN,
        )
        self.chat_area.pack(fill="both", expand=True)

        self.chat_area.tag_config("time",  foreground=TEXT_DIM,  font=FONT_SMALL)
        self.chat_area.tag_config("name",  foreground=ACCENT,    font=FONT_BOLD)
        self.chat_area.tag_config("prof",  foreground=YELLOW,    font=FONT_BOLD)
        self.chat_area.tag_config("msg",   foreground=TEXT_MAIN, font=FONT_MAIN)
        self.chat_area.tag_config("link",  foreground=TEXT_LINK, font=FONT_MAIN,
                                   underline=True)
        self.chat_area.tag_config("file",  foreground=GREEN,     font=FONT_MAIN)
        self.chat_area.tag_config("sys",   foreground=TEXT_DIM,  font=FONT_SMALL,
                                   justify="center")

        self.chat_area.tag_bind("link", "<Button-1>", self._open_link)
        self.chat_area.tag_bind("link", "<Enter>",
                                lambda e: self.chat_area.config(cursor="hand2"))
        self.chat_area.tag_bind("link", "<Leave>",
                                lambda e: self.chat_area.config(cursor="arrow"))

        self._link_map = {}  # tag -> url

        send_frame = tk.Frame(parent, bg=BG_DARK)
        send_frame.pack(fill="x", pady=(8, 0))

        btn_row = tk.Frame(send_frame, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(0, 6))

        self._btn(btn_row, "🔗 Enviar Link", self._send_link,
                  bg=ACCENT2).pack(side="left", padx=(0, 6))
        self._btn(btn_row, "📁 Enviar Arquivo", self._send_file,
                  bg=BG_CARD).pack(side="left")

        input_row = tk.Frame(send_frame, bg=BG_INPUT, bd=0,
                             highlightthickness=1,
                             highlightbackground=BG_CARD,
                             highlightcolor=ACCENT)
        input_row.pack(fill="x")

        self.msg_entry = tk.Entry(
            input_row, bg=BG_INPUT, fg=TEXT_MAIN, font=FONT_MAIN,
            bd=0, insertbackground=TEXT_MAIN,
            disabledbackground=BG_INPUT,
        )
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        self.msg_entry.bind("<Return>", lambda e: self._send_text())
        self.msg_entry.config(state="disabled")

        self._btn(input_row, "Enviar", self._send_text,
                  bg=ACCENT, padx=14).pack(side="right", padx=6, pady=4)

    def _build_sidebar(self, parent):
        self.toggle_btn = tk.Button(
            parent, text="▶  Iniciar Servidor",
            font=FONT_BOLD, bg=GREEN, fg="#0d1117",
            bd=0, pady=10, cursor="hand2",
            activebackground="#2fb87a", activeforeground="#0d1117",
            command=self._toggle_server,
        )
        self.toggle_btn.pack(fill="x", pady=(0, 12))

        self.ip_lbl = tk.Label(parent, text="", font=FONT_MONO,
                               bg=BG_DARK, fg=TEXT_DIM, wraplength=200,
                               justify="center")
        self.ip_lbl.pack(fill="x", pady=(0, 10))

        sep = tk.Frame(parent, bg=BG_CARD, height=1)
        sep.pack(fill="x", pady=(0, 10))

        tk.Label(parent, text="Alunos Conectados", font=FONT_BOLD,
                 bg=BG_DARK, fg=TEXT_DIM).pack(anchor="w", pady=(0, 4))

        list_frame = tk.Frame(parent, bg=BG_CARD, bd=0)
        list_frame.pack(fill="both", expand=True)

        self.client_list = tk.Listbox(
            list_frame, bg=BG_CARD, fg=TEXT_MAIN, font=FONT_MAIN,
            bd=0, selectbackground=ACCENT2, activestyle="none",
            highlightthickness=0,
        )
        self.client_list.pack(fill="both", expand=True, padx=4, pady=4)

        sep2 = tk.Frame(parent, bg=BG_CARD, height=1)
        sep2.pack(fill="x", pady=10)

        self.count_lbl = tk.Label(parent, text="0 aluno(s)", font=FONT_SMALL,
                                  bg=BG_DARK, fg=TEXT_DIM)
        self.count_lbl.pack()

    def _btn(self, parent, text, cmd, bg=BG_CARD, padx=10):
        return tk.Button(
            parent, text=text, command=cmd, font=FONT_SMALL,
            bg=bg, fg=TEXT_MAIN, bd=0, padx=padx, pady=5,
            cursor="hand2", activebackground=ACCENT, activeforeground=TEXT_MAIN,
        )

    # ─────────────────────────── Chat helpers ────────────────────────────────

    def _append_chat(self, entry: dict):
        """Insere uma mensagem formatada na área de chat."""
        self.chat_area.config(state="normal")
        kind = entry.get("kind")

        if kind == "sys":
            self.chat_area.insert("end", f"  {entry['text']}  \n", "sys")

        elif kind == "text":
            sender_tag = "prof" if entry.get("is_prof") else "name"
            self.chat_area.insert("end", f"[{entry['time']}] ", "time")
            self.chat_area.insert("end", f"{entry['sender']}: ", sender_tag)
            self.chat_area.insert("end", f"{entry['text']}\n", "msg")

        elif kind == "link":
            tag_id = f"link_{len(self._link_map)}"
            self._link_map[tag_id] = entry["url"]
            self.chat_area.insert("end", f"[{entry['time']}] ", "time")
            self.chat_area.insert("end", f"{entry['sender']}: ", "prof")
            self.chat_area.insert("end", f"🔗 {entry['url']}\n",
                                  ("link", tag_id))

        elif kind == "file":
            self.chat_area.insert("end", f"[{entry['time']}] ", "time")
            self.chat_area.insert("end", f"{entry['sender']}: ", "prof")
            self.chat_area.insert("end",
                                  f"📁 Arquivo enviado: {entry['filename']}\n",
                                  "file")

        self.chat_area.config(state="disabled")
        self.chat_area.see("end")

    def _open_link(self, event):
        tags = self.chat_area.tag_names("current")
        for t in tags:
            if t in self._link_map:
                import webbrowser
                webbrowser.open(self._link_map[t])
                break

    def _log_sys(self, text):
        entry = {"kind": "sys", "text": text}
        self.history.append(entry)
        self.root.after(0, self._append_chat, entry)

    # ─────────────────────────── Servidor ────────────────────────────────────

    def _toggle_server(self):
        if not self.running:
            self._start_server()
        else:
            self._stop_server()

    def _start_server(self):
        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind(("", TCP_PORT))
            self.server_sock.listen(50)
        except OSError as e:
            messagebox.showerror("Erro", f"Não foi possível iniciar o servidor:\n{e}")
            return

        self.running = True
        ip = self._get_local_ip()

        self.toggle_btn.config(text="■  Parar Servidor", bg=RED,
                               activebackground="#c84444")
        self.status_dot.config(fg=GREEN)
        self.status_lbl.config(text=f"Rodando em {ip}:{TCP_PORT}", fg=GREEN)
        self.ip_lbl.config(text=f"IP: {ip}")
        self.msg_entry.config(state="normal")

        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._udp_broadcast, daemon=True).start()

        self._log_sys(f"✦ Servidor iniciado — {ip}:{TCP_PORT}")

    def _stop_server(self):
        self.running = False
        self._broadcast_all({"kind": "server_close"})
        time.sleep(0.3)

        with self._lock:
            for info in list(self.clients.values()):
                try:
                    info["conn"].close()
                except Exception:
                    pass
            self.clients.clear()

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass

        self.history.clear()
        self._link_map.clear()

        # Limpar chat
        self.chat_area.config(state="normal")
        self.chat_area.delete("1.0", "end")
        self.chat_area.config(state="disabled")

        self.client_list.delete(0, "end")
        self.count_lbl.config(text="0 aluno(s)")

        self.toggle_btn.config(text="▶  Iniciar Servidor", bg=GREEN,
                               activebackground="#2fb87a")
        self.status_dot.config(fg=RED)
        self.status_lbl.config(text="Servidor desligado", fg=TEXT_DIM)
        self.ip_lbl.config(text="")
        self.msg_entry.config(state="disabled")

    def _accept_loop(self):
        while self.running:
            try:
                self.server_sock.settimeout(1.0)
                conn, addr = self.server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_client,
                             args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn: socket.socket, addr):
        try:
            raw = self._recv_msg(conn)
            if not raw:
                conn.close()
                return
            msg = json.loads(raw)
            name = msg.get("name", f"Aluno {addr[1]}")
        except Exception:
            conn.close()
            return

        with self._lock:
            self.clients[addr] = {"conn": conn, "name": name, "addr": addr}

        self.root.after(0, self._refresh_client_list)
        self._log_sys(f"→ {name} entrou na aula")

        for entry in list(self.history):
            if entry.get("kind") != "sys":
                try:
                    self._send_msg(conn, json.dumps(entry))
                except Exception:
                    break

        # Loop de leitura (clientes não enviam mensagens neste protocolo,
        # mas mantemos a conexão aberta)
        try:
            while self.running:
                conn.settimeout(5.0)
                try:
                    data = self._recv_msg(conn)
                    if data is None:
                        break
                except socket.timeout:
                    continue
        except Exception:
            pass
        finally:
            conn.close()
            with self._lock:
                self.clients.pop(addr, None)
            self.root.after(0, self._refresh_client_list)
            self._log_sys(f"← {name} saiu")

    def _udp_broadcast(self):
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            return

        payload = json.dumps({
            "type": "lan_chat_server",
            "port": TCP_PORT,
            "ip": self._get_local_ip(),
        }).encode()

        while self.running:
            try:
                self.udp_sock.sendto(payload, ("<broadcast>", UDP_PORT))
            except Exception:
                pass
            time.sleep(BROADCAST_INTERVAL)

        try:
            self.udp_sock.close()
        except Exception:
            pass

    # ─────────────────────────── Envio de mensagens ──────────────────────────

    def _send_text(self):
        text = self.msg_entry.get().strip()
        if not text or not self.running:
            return
        self.msg_entry.delete(0, "end")

        entry = {
            "kind": "text",
            "sender": "Professor",
            "is_prof": True,
            "text": text,
            "time": now_str(),
        }
        self.history.append(entry)
        self._append_chat(entry)
        self._broadcast_all(entry)

    def _send_link(self):
        if not self.running:
            messagebox.showwarning("Aviso", "Inicie o servidor primeiro.")
            return
        win = tk.Toplevel(self.root)
        win.title("Enviar Link")
        win.configure(bg=BG_DARK)
        win.geometry("420x140")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="URL para enviar:", font=FONT_BOLD,
                 bg=BG_DARK, fg=TEXT_MAIN).pack(padx=16, pady=(16, 4), anchor="w")

        entry_var = tk.StringVar()
        e = tk.Entry(win, textvariable=entry_var, font=FONT_MAIN,
                     bg=BG_INPUT, fg=TEXT_MAIN, bd=0, insertbackground=TEXT_MAIN,
                     width=46)
        e.pack(padx=16, pady=4)
        e.insert(0, "https://")
        e.focus_set()

        def do_send():
            url = entry_var.get().strip()
            if not url or url == "https://":
                return
            win.destroy()
            entry = {
                "kind": "link",
                "sender": "Professor",
                "is_prof": True,
                "url": url,
                "time": now_str(),
            }
            self.history.append(entry)
            self._append_chat(entry)
            self._broadcast_all(entry)

        e.bind("<Return>", lambda _: do_send())
        self._btn(win, "Enviar Link", do_send, bg=ACCENT, padx=20).pack(pady=8)

    def _send_file(self):
        if not self.running:
            messagebox.showwarning("Aviso", "Inicie o servidor primeiro.")
            return
        path = filedialog.askopenfilename(title="Selecionar arquivo para enviar")
        if not path:
            return

        size = os.path.getsize(path)
        if size > MAX_FILE_SIZE:
            messagebox.showerror("Erro",
                                 f"Arquivo muito grande (máx. 50 MB).\n"
                                 f"Tamanho: {size // 1024 // 1024} MB")
            return

        filename = os.path.basename(path)
        with open(path, "rb") as f:
            data_b64 = base64.b64encode(f.read()).decode()

        entry = {
            "kind": "file",
            "sender": "Professor",
            "is_prof": True,
            "filename": filename,
            "data": data_b64,
            "time": now_str(),
        }
        self.history.append(entry)
        self._append_chat(entry)
        self._broadcast_all(entry)

    def _broadcast_all(self, msg: dict):
        raw = json.dumps(msg)
        with self._lock:
            dead = []
            for addr, info in self.clients.items():
                try:
                    self._send_msg(info["conn"], raw)
                except Exception:
                    dead.append(addr)
            for a in dead:
                self.clients.pop(a, None)

    # ─────────────────────────── Protocolo de framing ───────────────────────

    @staticmethod
    def _send_msg(conn: socket.socket, data: str):
        encoded = data.encode("utf-8")
        header = struct.pack(">I", len(encoded))
        conn.sendall(header + encoded)

    @staticmethod
    def _recv_msg(conn: socket.socket):
        raw_len = ServerApp._recvall(conn, 4)
        if not raw_len:
            return None
        length = struct.unpack(">I", raw_len)[0]
        data = ServerApp._recvall(conn, length)
        if not data:
            return None
        return data.decode("utf-8")

    @staticmethod
    def _recvall(conn: socket.socket, n: int):
        buf = b""
        while len(buf) < n:
            try:
                chunk = conn.recv(n - len(buf))
            except Exception:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf

    # ─────────────────────────── Utilidades ──────────────────────────────────

    def _refresh_client_list(self):
        self.client_list.delete(0, "end")
        with self._lock:
            names = [v["name"] for v in self.clients.values()]
        for n in names:
            self.client_list.insert("end", f"  {n}")
        self.count_lbl.config(text=f"{len(names)} aluno(s)")

    @staticmethod
    def _get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _on_close(self):
        if self.running:
            if messagebox.askyesno("Sair",
                                   "O servidor está rodando. Deseja parar e sair?"):
                self._stop_server()
                self.root.destroy()
        else:
            self.root.destroy()


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    root.mainloop()
