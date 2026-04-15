import os
import base64
import secrets
import time
import requests
from flask import Flask, request, redirect, jsonify, render_template_string

app = Flask(__name__)

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO — define estas no dashboard do Render como
# Environment Variables (nunca hardcodes secrets no código)
# ──────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID",     "SEU_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "SEU_CLIENT_SECRET")
GUILD_ID      = os.getenv("DISCORD_GUILD_ID",      "ID_DO_SERVIDOR")
REQUIRED_ROLE = os.getenv("DISCORD_REQUIRED_ROLE", "ID_DO_CARGO")
BOT_TOKEN     = os.getenv("DISCORD_BOT_TOKEN",     "SEU_BOT_TOKEN")
BASE_URL      = os.getenv("BASE_URL", "https://o-teu-app.onrender.com")
# ──────────────────────────────────────────────────────────────

REDIRECT_URI = f"{BASE_URL}/callback"
DISCORD_API  = "https://discord.com/api/v10"
TOKEN_TTL    = 300  # segundos (5 minutos)

# Sessões em memória: token -> { status, username, b64id, ts }
sessions: dict = {}


def clean_old_sessions():
    now     = time.time()
    expired = [t for t, v in sessions.items() if now - v["ts"] > TOKEN_TTL]
    for t in expired:
        del sessions[t]


# ─────────────────── HTML ─────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CS2 Loader — Autenticação</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
<style>
  :root{--red:#e63946;--red-dim:#7d1a20;--green:#2cffa0;--bg:#080b0f;--panel:#0d1117;--border:#1e2a38;--text:#c9d6e3;}
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:var(--bg);font-family:'Share Tech Mono',monospace;color:var(--text);
       height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden;}
  body::before{content:'';position:fixed;inset:0;
    background-image:linear-gradient(rgba(46,213,115,.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(46,213,115,.04) 1px,transparent 1px);
    background-size:40px 40px;pointer-events:none;}
  .corner{position:fixed;width:100px;height:100px;border-color:var(--red);border-style:solid;opacity:.28;}
  .corner.tl{top:16px;left:16px;border-width:2px 0 0 2px;}
  .corner.tr{top:16px;right:16px;border-width:2px 2px 0 0;}
  .corner.bl{bottom:16px;left:16px;border-width:0 0 2px 2px;}
  .corner.br{bottom:16px;right:16px;border-width:0 2px 2px 0;}
  .panel{background:var(--panel);border:1px solid var(--border);padding:44px 48px;
         width:400px;position:relative;animation:fadeIn .4s ease;}
  .panel::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--red);}
  @keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
  .tag{font-size:10px;letter-spacing:3px;color:var(--red);text-transform:uppercase;margin-bottom:10px;}
  h1{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;color:#fff;letter-spacing:1px;margin-bottom:4px;}
  .sub{font-size:11px;color:#3a4a5a;margin-bottom:28px;letter-spacing:1px;}
  .token-box{background:#060a0e;border:1px solid #1e2a38;padding:10px 14px;margin-bottom:28px;}
  .token-label{color:#3a4a5a;letter-spacing:2px;font-size:9px;text-transform:uppercase;margin-bottom:5px;}
  .token-val{color:var(--green);font-size:11px;word-break:break-all;letter-spacing:1px;}
  .discord-btn{display:flex;align-items:center;justify-content:center;gap:12px;width:100%;
               padding:14px;background:#5865F2;border:none;color:#fff;font-family:'Rajdhani',sans-serif;
               font-size:14px;font-weight:600;letter-spacing:1px;cursor:pointer;
               text-decoration:none;transition:background .2s;}
  .discord-btn:hover{background:#4752c4;}
  .discord-btn svg{width:18px;height:18px;flex-shrink:0;}
  .status-bar{margin-top:24px;padding-top:16px;border-top:1px solid var(--border);
              display:flex;align-items:center;gap:8px;font-size:9px;letter-spacing:1px;color:#2a3a4a;}
  .dot{width:5px;height:5px;border-radius:50%;background:var(--red);animation:pulse 1.5s infinite;flex-shrink:0;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  .error-box{background:#1a0608;border:1px solid var(--red-dim);color:var(--red);
             font-size:11px;padding:10px 14px;margin-bottom:18px;}
</style>
</head>
<body>
<div class="corner tl"></div><div class="corner tr"></div>
<div class="corner bl"></div><div class="corner br"></div>
<div class="panel">
  <div class="tag">// acesso restrito</div>
  <h1>CS2 LOADER</h1>
  <p class="sub">AUTENTICAÇÃO OBRIGATÓRIA · v3.0</p>
  {% if error %}<div class="error-box">! {{ error }}</div>{% endif %}
  <div class="token-box">
    <div class="token-label">Session Token</div>
    <div class="token-val">{{ token }}</div>
  </div>
  <a href="{{ oauth_url }}" class="discord-btn">
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
    </svg>
    ENTRAR COM DISCORD
  </a>
  <div class="status-bar">
    <div class="dot"></div>
    <span>AGUARDANDO · TOKEN EXPIRA EM 5 MIN</span>
  </div>
</div>
</body>
</html>"""

SUCCESS_HTML = """<!DOCTYPE html>
<html lang="pt"><head><meta charset="UTF-8"><title>Acesso Autorizado</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@700&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:#080b0f;font-family:'Share Tech Mono',monospace;color:#2cffa0;
       height:100vh;display:flex;align-items:center;justify-content:center;}
  .box{text-align:center;}
  .icon{font-size:52px;margin-bottom:16px;}
  h2{font-family:'Rajdhani',sans-serif;font-size:22px;letter-spacing:3px;color:#fff;margin-bottom:8px;}
  p{font-size:11px;letter-spacing:2px;opacity:.5;}
  .ok{color:#2cffa0;font-size:10px;margin-top:20px;letter-spacing:1px;}
</style></head><body>
<div class="box">
  <div class="icon">&#x2713;</div>
  <h2>ACESSO AUTORIZADO</h2>
  <p>Cargo verificado com sucesso.</p>
  <p class="ok">Podes fechar esta janela.</p>
</div></body></html>"""

DENIED_HTML = """<!DOCTYPE html>
<html lang="pt"><head><meta charset="UTF-8"><title>Acesso Negado</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@700&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{background:#080b0f;font-family:'Share Tech Mono',monospace;color:#e63946;
       height:100vh;display:flex;align-items:center;justify-content:center;}
  .box{text-align:center;}
  .icon{font-size:52px;margin-bottom:16px;}
  h2{font-family:'Rajdhani',sans-serif;font-size:22px;letter-spacing:3px;color:#fff;margin-bottom:8px;}
  p{font-size:11px;letter-spacing:2px;opacity:.5;}
  .err{color:#e63946;font-size:10px;margin-top:20px;letter-spacing:1px;}
</style></head><body>
<div class="box">
  <div class="icon">&#x2717;</div>
  <h2>ACESSO NEGADO</h2>
  <p>Não tens o cargo necessário.</p>
  <p class="err">Podes fechar esta janela.</p>
</div></body></html>"""


# ─────────────────── ROTAS ────────────────────────────────────

@app.route("/session", methods=["POST"])
def create_session():
    """C# chama isto primeiro para obter um token único."""
    clean_old_sessions()
    token = secrets.token_urlsafe(24)
    sessions[token] = {"status": "pending", "username": "", "b64id": "", "ts": time.time()}
    return jsonify({"token": token})


@app.route("/login")
def login():
    """C# abre o browser aqui com ?token=XXXX"""
    token = request.args.get("token", "")
    error = request.args.get("error", "")
    clean_old_sessions()

    if not token or token not in sessions:
        return "<h2 style='font-family:monospace;color:#e63946;background:#080b0f;height:100vh;display:flex;align-items:center;justify-content:center;'>Token inválido ou expirado.</h2>", 400

    oauth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify+guilds.members.read"
        f"&state={token}"
    )
    return render_template_string(LOGIN_HTML, token=token, oauth_url=oauth_url, error=error)


@app.route("/status")
def status():
    """C# faz polling aqui: GET /status?token=XXXX"""
    token = request.args.get("token", "")
    if not token or token not in sessions:
        return jsonify({"status": "expired"})

    s = sessions[token]
    if time.time() - s["ts"] > TOKEN_TTL:
        del sessions[token]
        return jsonify({"status": "expired"})

    return jsonify({
        "status":   s["status"],
        "username": s.get("username", ""),
        "b64id":    s.get("b64id", ""),
    })


@app.route("/callback")
def callback():
    """Discord redireciona aqui após o OAuth."""
    code  = request.args.get("code", "")
    token = request.args.get("state", "")  # token passou pelo OAuth state

    if not code or not token or token not in sessions:
        return render_template_string(DENIED_HTML)

    # 1. Trocar code por access_token
    tr = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if tr.status_code != 200:
        sessions[token]["status"] = "denied"
        return render_template_string(DENIED_HTML)

    access_token = tr.json().get("access_token")

    # 2. Dados do utilizador
    ur = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if ur.status_code != 200:
        sessions[token]["status"] = "denied"
        return render_template_string(DENIED_HTML)

    user     = ur.json()
    user_id  = user["id"]
    username = user.get("username", "?")
    b64id    = base64.b64encode(user_id.encode()).decode()

    # 3. Verificar cargo via bot
    mr = requests.get(
        f"{DISCORD_API}/guilds/{GUILD_ID}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
    )
    has_role = mr.status_code == 200 and REQUIRED_ROLE in mr.json().get("roles", [])

    # 4. Atualizar sessão — o C# vai detetar pelo /status
    sessions[token].update({
        "status":   "ok" if has_role else "denied",
        "username": username,
        "b64id":    b64id,
        "ts":       time.time(),
    })

    return render_template_string(SUCCESS_HTML if has_role else DENIED_HTML)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
