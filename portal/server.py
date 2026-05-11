import os
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse


def _app_cards() -> list[dict[str, str | bool]]:
    items = [
        {
            "name": "MarketingHub",
            "summary": "Marketing flows, segmentation, sync and outbound operations.",
            "url": os.getenv("PORTAL_MARKETINGHUB_URL", "").strip(),
            "host": "External",
        },
        {
            "name": "OWIS",
            "summary": "Offshore wind monitoring, news review and source operations.",
            "url": os.getenv("PORTAL_OWIS_URL", "").strip(),
            "host": "External",
        },
        {
            "name": "Opportunities",
            "summary": "Tender and opportunity screening with prioritised follow-up.",
            "url": os.getenv("PORTAL_OPPORTUNITIES_URL", "").strip(),
            "host": "External",
        },
        {
            "name": "Umamu",
            "summary": "Umamu application entry point.",
            "url": os.getenv("PORTAL_UMAMU_URL", "").strip(),
            "host": "External",
        },
    ]
    for item in items:
        item["status"] = bool(item["url"])
    return items


def _render_index() -> str:
    title = os.getenv("PORTAL_TITLE", "NorthernBlue App Portal").strip() or "NorthernBlue App Portal"
    intro = os.getenv(
        "PORTAL_INTRO",
        "One clean front door for the apps we build and run. Keep one stable landing page and jump straight into the right tool.",
    ).strip()
    home_url = os.getenv("PORTAL_HOME_URL", "https://northernblue.eu").strip() or "https://northernblue.eu"
    about_url = os.getenv("PORTAL_ABOUT_URL", "https://northernblue.eu/about").strip() or "https://northernblue.eu/about"
    contact_url = os.getenv("PORTAL_CONTACT_URL", "https://northernblue.eu/contact").strip() or "https://northernblue.eu/contact"

    cards = []
    for item in _app_cards():
        url = str(item["url"])
        is_live = bool(item["status"])
        initial = escape(str(item["name"])[:1] or "A")
        action = (
            f'<a class="cta" href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">Open app</a>'
            if is_live
            else '<span class="cta cta-disabled">URL missing</span>'
        )
        cards.append(
            f"""
            <article class="card">
              <div class="card-top">
                <div>
                  <div class="orb">{initial}</div>
                  <p class="eyebrow">{escape(str(item["host"]))}</p>
                  <h2>{escape(str(item["name"]))}</h2>
                </div>
                <span class="badge {'badge-live' if is_live else 'badge-missing'}">{'Live' if is_live else 'Missing URL'}</span>
              </div>
              <p class="summary">{escape(str(item["summary"]))}</p>
              {action}
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      --page: #06101d;
      --page-top: #0a1424;
      --page-bottom: #040914;
      --ink: #eef6ff;
      --muted: rgba(220,232,248,0.74);
      --line: rgba(148, 184, 224, 0.14);
      --panel: rgba(10, 19, 34, 0.56);
      --panel-strong: rgba(13, 25, 44, 0.72);
      --accent: #60a5fa;
      --accent-soft: rgba(96,165,250,0.16);
      --accent-strong: #93c5fd;
      --live-bg: rgba(96,165,250,0.12);
      --warn-bg: rgba(245, 158, 11, 0.12);
      --warn-ink: #fcd34d;
      --footer: rgba(5, 11, 21, 0.86);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 12%, rgba(96,165,250,0.18), transparent 24%),
        radial-gradient(circle at 82% 18%, rgba(45,212,191,0.12), transparent 20%),
        radial-gradient(circle at 50% 100%, rgba(59,130,246,0.10), transparent 26%),
        linear-gradient(180deg, var(--page-top) 0%, var(--page) 44%, var(--page-bottom) 100%);
    }}
    a {{
      color: inherit;
    }}
    .shell {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      border-bottom: 1px solid var(--line);
      background: rgba(6, 16, 29, 0.62);
      backdrop-filter: blur(18px) saturate(140%);
    }}
    .topbar-inner {{
      max-width: 1160px;
      margin: 0 auto;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .brand {{
      text-decoration: none;
      font: 700 1.05rem/1 "Segoe UI", Tahoma, sans-serif;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--ink);
      text-shadow: 0 0 20px rgba(96,165,250,0.16);
    }}
    .brand span {{
      color: var(--accent);
    }}
    .topnav {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      font: 600 0.92rem/1.2 "Segoe UI", Tahoma, sans-serif;
      color: rgba(220,232,248,0.66);
    }}
    .topnav a {{
      text-decoration: none;
    }}
    .topnav a:hover {{
      color: #dbeafe;
    }}
    .wrap {{
      max-width: 1160px;
      margin: 0 auto;
      padding: 64px 24px 84px;
    }}
    .eyebrow {{
      margin: 0 0 14px;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font: 700 0.75rem/1.2 "Segoe UI", Tahoma, sans-serif;
    }}
    .hero {{
      max-width: 860px;
      margin-bottom: 48px;
      position: relative;
      padding: 30px 32px;
      border: 1px solid rgba(148, 184, 224, 0.12);
      border-radius: 28px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)),
        var(--panel);
      backdrop-filter: blur(18px) saturate(150%);
      box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05),
        0 24px 70px rgba(0,0,0,0.26);
    }}
    h1 {{
      margin: 0;
      max-width: 9ch;
      font-size: clamp(3rem, 5vw, 5.4rem);
      line-height: 0.92;
      font-weight: 700;
      letter-spacing: -0.04em;
    }}
    .lead {{
      max-width: 62ch;
      margin: 20px 0 0;
      color: var(--muted);
      font: 400 1.08rem/1.8 "Segoe UI", Tahoma, sans-serif;
    }}
    .intro-strip {{
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid var(--line);
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      color: var(--muted);
      font: 600 0.88rem/1.5 "Segoe UI", Tahoma, sans-serif;
    }}
    .intro-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 18px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--line);
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 2rem;
      letter-spacing: -0.03em;
    }}
    .section-head p {{
      margin: 0;
      max-width: 48ch;
      color: var(--muted);
      text-align: right;
      font: 400 0.95rem/1.6 "Segoe UI", Tahoma, sans-serif;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      border-top: 0;
    }}
    .card {{
      padding: 28px 26px 26px;
      min-height: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      border: 1px solid var(--line);
      border-radius: 22px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)),
        var(--panel);
      backdrop-filter: blur(20px) saturate(150%);
      box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.04),
        0 18px 48px rgba(0,0,0,0.22);
      transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, background 160ms ease;
    }}
    .card:hover {{
      transform: translateY(-4px);
      border-color: rgba(147,197,253,0.26);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03)),
        var(--panel-strong);
      box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05),
        0 24px 64px rgba(0,0,0,0.28),
        0 0 0 1px rgba(96,165,250,0.05);
    }}
    .orb {{
      width: 38px;
      height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      margin-bottom: 14px;
      color: #dbeafe;
      background: linear-gradient(135deg, rgba(96,165,250,0.26), rgba(45,212,191,0.14));
      border: 1px solid rgba(148, 184, 224, 0.18);
      box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.08),
        0 10px 24px rgba(96,165,250,0.12);
      font: 700 0.88rem/1 "Segoe UI", Tahoma, sans-serif;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
    }}
    .card h2 {{
      margin: 0;
      font-size: 1.6rem;
      letter-spacing: -0.03em;
    }}
    .summary {{
      margin: 14px 0 18px;
      color: var(--muted);
      max-width: 48ch;
      font: 400 0.96rem/1.72 "Segoe UI", Tahoma, sans-serif;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 9px;
      white-space: nowrap;
      font: 700 0.74rem/1 "Segoe UI", Tahoma, sans-serif;
      border: 1px solid transparent;
    }}
    .badge-live {{
      color: #dbeafe;
      background: var(--live-bg);
      border-color: rgba(96,165,250,0.16);
    }}
    .badge-missing {{
      color: var(--warn-ink);
      background: var(--warn-bg);
      border-color: rgba(245,158,11,0.14);
    }}
    .cta {{
      display: inline-flex;
      width: fit-content;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 10px 14px;
      text-decoration: none;
      border: 1px solid rgba(148, 184, 224, 0.16);
      background: rgba(255,255,255,0.04);
      color: #eff6ff;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
      font: 700 0.92rem/1.2 "Segoe UI", Tahoma, sans-serif;
    }}
    .cta-disabled {{
      border-color: rgba(148, 184, 224, 0.10);
      color: rgba(220,232,248,0.42);
      cursor: default;
    }}
    .footer {{
      margin-top: auto;
      background: var(--footer);
      border-top: 1px solid rgba(148, 184, 224, 0.10);
      color: rgba(255,255,255,0.72);
    }}
    .footer-inner {{
      max-width: 1160px;
      margin: 0 auto;
      padding: 26px 24px 30px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      font: 400 0.9rem/1.6 "Segoe UI", Tahoma, sans-serif;
    }}
    .footer a {{
      color: var(--accent-strong);
      text-decoration: none;
    }}
    @media (max-width: 860px) {{
      .topbar-inner,
      .section-head,
      .footer-inner {{
        flex-direction: column;
        align-items: flex-start;
      }}
      .wrap {{
        padding: 24px 16px 40px;
      }}
      h1 {{
        max-width: none;
      }}
      .section-head p {{
        text-align: left;
      }}
      .grid {{
        grid-template-columns: 1fr;
      }}
      .card {{
        padding: 22px 18px;
      }}
      .hero {{
        padding: 24px 20px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-inner">
        <a class="brand" href="{escape(home_url, quote=True)}" target="_blank" rel="noopener noreferrer">Northern<span>Blue</span></a>
        <nav class="topnav" aria-label="NorthernBlue navigation">
          <a href="{escape(home_url, quote=True)}" target="_blank" rel="noopener noreferrer">Home</a>
          <a href="{escape(about_url, quote=True)}" target="_blank" rel="noopener noreferrer">About</a>
          <a href="{escape(contact_url, quote=True)}" target="_blank" rel="noopener noreferrer">Contact</a>
        </nav>
      </div>
    </header>
    <main class="wrap">
      <section class="hero">
        <p class="eyebrow">Shared Entry Point</p>
        <h1>{escape(title)}</h1>
        <p class="lead">{escape(intro)}</p>
        <div class="intro-strip">
          <span class="intro-pill">Independent advisory</span>
          <span class="intro-pill">Operational tools</span>
          <span class="intro-pill">One canonical entry point</span>
        </div>
      </section>
      <section>
        <div class="section-head">
          <h2>Applications</h2>
          <p>Fast access to the systems behind NorthernBlue operations, market intelligence, outreach, and analytics.</p>
        </div>
        <div class="grid">
          {''.join(cards)}
        </div>
      </section>
    </main>
    <footer class="footer">
      <div class="footer-inner">
        <span>NorthernBlue is an independent offshore wind advisory firm based in Haugesund, Norway.</span>
        <a href="{escape(contact_url, quote=True)}" target="_blank" rel="noopener noreferrer">Get in touch</a>
      </div>
    </footer>
  </div>
</body>
</html>"""


class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/", "/index.html"):
            html = _render_index().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        body = b"Not found"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), PortalHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
