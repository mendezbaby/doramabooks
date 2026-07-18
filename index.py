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
from datetime import datetime, timezone
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


# ---------- compras identificadas por e-mail ----------
def email_base(email):
    """external_id base derivado do e-mail do comprador."""
    return "doramasbook-" + email.strip().lower()[:60]


def lookup_email_transactions(email):
    """Retorna (lista_de_(ext, tx)_existentes, primeiro_external_id_livre).
    Tenta doramasbook-<email>, -2, -3... ate achar um que nao existe (404)."""
    base = email_base(email)
    found = []
    free_ext = None
    for suffix in ["", "-2", "-3", "-4", "-5"]:
        ext = base + suffix
        status, data = nexuspag_request("GET", "/api/pix/" + urllib.parse.quote(ext, safe=""))
        if status == 404 or not isinstance(data, dict) or "status" not in data:
            free_ext = ext
            break
        found.append((ext, data))
    return found, free_ext


def tx_still_valid(tx):
    """Transacao pendente ainda pode ser paga (nao passou do expires_at)?"""
    exp = tx.get("expires_at")
    if not exp:
        return True
    try:
        return datetime.fromisoformat(str(exp).replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except Exception:
        return False


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

    # ---------- POST /api/create-pix  |  /api/recover ----------
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            client_body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            client_body = {}

        if self.path.startswith("/api/create-pix"):
            self._handle_create_pix(client_body)
        elif self.path.startswith("/api/recover"):
            self._handle_recover(client_body)
        else:
            self._send_json(404, {"success": False, "error": "Rota nao encontrada"})

    def _get_email(self, body):
        email = (body.get("email") or "").strip().lower()
        if not email or "@" not in email or "." not in email:
            return None
        return email

    def _handle_create_pix(self, client_body):
        email = self._get_email(client_body)
        if not email:
            self._send_json(400, {"success": False, "error": "Informe um e-mail valido."})
            return

        found, free_ext = lookup_email_transactions(email)

        # 1) ja pagou alguma vez? -> libera direto, sem cobrar de novo
        for ext, tx in found:
            if tx.get("status") == "paid":
                self._send_json(200, {"success": True, "already_paid": True, "transaction": tx})
                return

        # 2) existe cobranca pendente e ainda valida? -> reutiliza o QR
        for ext, tx in found:
            if tx.get("status") == "pending" and tx_still_valid(tx):
                self._send_json(200, {"success": True, "transaction": tx})
                return

        # 3) cria cobranca nova num external_id livre
        if not free_ext:
            self._send_json(409, {"success": False, "error": "Muitas tentativas. Fale com o suporte."})
            return
        payload = {
            "amount": EBOOK_PRICE,
            "description": EBOOK_DESCRIPTION,
            "external_id": free_ext,
            "expiration": 1800,
        }
        status, data = nexuspag_request("POST", "/api/pix/create", payload)
        self._send_json(status, data)

    def _handle_recover(self, client_body):
        email = self._get_email(client_body)
        if not email:
            self._send_json(400, {"success": False, "error": "Informe um e-mail valido."})
            return
        found, _ = lookup_email_transactions(email)
        paid = any(tx.get("status") == "paid" for _, tx in found)
        self._send_json(200, {"success": True, "paid": paid})

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
