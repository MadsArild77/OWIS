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
      --page: #ffffff;
      --ink: #0c1a2b;
      --muted: rgba(12,26,43,0.64);
      --line: #e2e8f0;
      --accent: #0ea5e9;
      --accent-soft: rgba(14,165,233,0.12);
      --accent-strong: #0284c7;
      --live-bg: rgba(14,165,233,0.10);
      --warn-bg: #fff7ed;
      --warn-ink: #9a3412;
      --footer: #0c1a2b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background: var(--page);
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
      border-bottom: 1px solid var(--line);
      background: #fff;
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
    }}
    .brand span {{
      color: var(--accent);
    }}
    .topnav {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      font: 600 0.92rem/1.2 "Segoe UI", Tahoma, sans-serif;
      color: var(--muted);
    }}
    .topnav a {{
      text-decoration: none;
    }}
    .topnav a:hover {{
      color: var(--accent-strong);
    }}
    .wrap {{
      max-width: 1160px;
      margin: 0 auto;
      padding: 56px 24px 72px;
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
      margin-bottom: 44px;
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
      background: #f8fafc;
      border: 1px solid var(--line);
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
      gap: 0;
      border-top: 1px solid var(--line);
    }}
    .card {{
      padding: 28px 0 28px 26px;
      min-height: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
      border-left: 4px solid transparent;
      transition: border-color 160ms ease, background 160ms ease;
    }}
    .card:hover {{
      border-left-color: var(--accent);
      background: linear-gradient(90deg, rgba(14,165,233,0.04), rgba(14,165,233,0));
    }}
    .orb {{
      width: 34px;
      height: 34px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      margin-bottom: 14px;
      color: var(--accent-strong);
      background: var(--accent-soft);
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
      border-radius: 4px;
      padding: 6px 9px;
      white-space: nowrap;
      font: 700 0.74rem/1 "Segoe UI", Tahoma, sans-serif;
    }}
    .badge-live {{
      color: var(--accent-strong);
      background: var(--live-bg);
    }}
    .badge-missing {{
      color: var(--warn-ink);
      background: var(--warn-bg);
    }}
    .cta {{
      display: inline-flex;
      width: fit-content;
      align-items: center;
      gap: 8px;
      border-radius: 0;
      padding: 0 0 4px;
      text-decoration: none;
      border-bottom: 2px solid var(--accent);
      color: var(--accent-strong);
      font: 700 0.92rem/1.2 "Segoe UI", Tahoma, sans-serif;
    }}
    .cta-disabled {{
      border-bottom-color: #cbd5e1;
      color: #94a3b8;
      cursor: default;
    }}
    .footer {{
      margin-top: auto;
      background: var(--footer);
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
      color: #fff;
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
        padding-left: 18px;
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
