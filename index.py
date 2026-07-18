# -*- coding: utf-8 -*-
"""
DORAMAS BOOK — entrypoint da Vercel (index:handler)
----------------------------------------------------
Um unico handler que:
  - serve o site estatico (index.html, css, js, assets)
  - POST /api/create-pix      -> cria cobranca PIX na NexusPag
  - GET  /api/pix-status?id=  -> consulta status do pagamento
A API key fica segura aqui no backend (nunca no navegador).
"""

import json
import os
import shutil
import subprocess
import urllib.parse
from http.server import SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))

# ===================== CONFIGURACOES =====================
NEXUSPAG_API_KEY = os.environ.get(
    "NEXUSPAG_API_KEY",
    "nxp_live_4fd4ead6c9ba9405affbc7fd09f3367c3d85c3be4f2747fd377af5a1fde0723e",
)
NEXUSPAG_BASE = "https://nexuspag.com"
EBOOK_PRICE = 6.00
EBOOK_DESCRIPTION = "DORAMAS BOOK - E-book: O Guarda-Chuva Que Ela Esqueceu"
# =========================================================

# O Cloudflare da NexusPag bloqueia o TLS padrao do Python.
# 1) curl_cffi (instalado via pyproject.toml na Vercel) imita o Chrome.
# 2) fallback: curl do sistema (funciona no Windows local).
try:
    from curl_cffi import requests as _cffi
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

CURL = shutil.which("curl") or "curl"

_HEADERS = {
    "x-api-key": NEXUSPAG_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def nexuspag_request(method, path, payload=None):
    """Chamada server-to-server para a API da NexusPag."""
    url = NEXUSPAG_BASE + path

    # 1) curl_cffi (TLS de navegador)
    if HAS_CFFI:
        try:
            r = _cffi.request(method, url, json=payload, headers=_HEADERS,
                              timeout=30, impersonate="chrome")
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {"success": False, "error": r.text[:500]}
        except Exception:
            pass

    # 2) curl do sistema (fallback local)
    cmd = [
        CURL, "-s", "-o", "-", "-w", "\n%{http_code}",
        "-X", method, url,
        "-H", "x-api-key: " + NEXUSPAG_API_KEY,
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "--max-time", "30",
    ]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", timeout=40)
        body, _, status = (out.stdout or "").rpartition("\n")
        try:
            return int(status), json.loads(body)
        except json.JSONDecodeError:
            return 502, {"success": False, "error": body or out.stderr or "sem resposta"}
    except Exception as e:
        return 502, {"success": False, "error": str(e)}


class handler(SimpleHTTPRequestHandler):
    """Estaticos (da pasta do projeto) + rotas /api/*."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # ---------- helpers ----------
    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------- POST /api/create-pix ----------
    def do_POST(self):
        if self.path.startswith("/api/create-pix"):
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                client_body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                client_body = {}

            payload = {
                "amount": EBOOK_PRICE,
                "description": EBOOK_DESCRIPTION,
                "external_id": client_body.get("external_id"),
                "expiration": 1800,
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            status, data = nexuspag_request("POST", "/api/pix/create", payload)
            self._send_json(status, data)
        else:
            self._send_json(404, {"success": False, "error": "Rota nao encontrada"})

    # ---------- GET /api/pix-status?id=...  |  estaticos ----------
    def do_GET(self):
        if self.path.startswith("/api/pix-status"):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            txid = (qs.get("id", [""])[0] or parsed.path.rsplit("/", 1)[-1]).strip()
            if not txid or txid == "pix-status":
                self._send_json(400, {"success": False, "error": "ID invalido"})
                return
            status, data = nexuspag_request("GET", "/api/pix/" + txid)
            self._send_json(status, data)
        else:
            super().do_GET()  # index.html, css, js, assets...

    # ---------- headers extras ----------
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
