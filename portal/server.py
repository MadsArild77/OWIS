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
              <div class="orb">{initial}</div>
              <div class="card-top">
                <div>
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
      --bg: #f4efe6;
      --bg-soft: #fbf8f2;
      --ink: #16233b;
      --muted: #5f6c83;
      --panel: rgba(255,255,255,0.82);
      --line: rgba(22,35,59,0.10);
      --brand: #0f766e;
      --brand-strong: #115e59;
      --warning: #9a3412;
      --warning-bg: #fff1e7;
      --live-bg: #ecfdf5;
      --shadow: 0 24px 60px rgba(22,35,59,0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.18), transparent 30%),
        radial-gradient(circle at 85% 18%, rgba(217,119,6,0.14), transparent 22%),
        radial-gradient(circle at 50% 100%, rgba(22,35,59,0.06), transparent 26%),
        linear-gradient(180deg, var(--bg-soft) 0%, var(--bg) 100%);
    }}
    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 40px 24px 64px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.4fr 0.8fr;
      gap: 24px;
      align-items: stretch;
      margin-bottom: 24px;
    }}
    .hero-panel, .meta-panel, .card {{
      border: 1px solid var(--line);
      border-radius: 28px;
      background: var(--panel);
      backdrop-filter: blur(12px);
      box-shadow: var(--shadow);
    }}
    .hero-panel {{
      position: relative;
      overflow: hidden;
      padding: 32px;
    }}
    .meta-panel {{
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .hero-panel::before {{
      content: "";
      position: absolute;
      inset: auto -60px -70px auto;
      width: 220px;
      height: 220px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(15,118,110,0.22), rgba(15,118,110,0));
      pointer-events: none;
    }}
    .hero-panel::after {{
      content: "";
      position: absolute;
      top: 22px;
      right: 22px;
      width: 86px;
      height: 86px;
      border-radius: 24px;
      border: 1px solid rgba(17,94,89,0.16);
      background: linear-gradient(180deg, rgba(255,255,255,0.7), rgba(236,253,245,0.72));
      transform: rotate(10deg);
    }}
    .eyebrow {{
      margin: 0 0 10px;
      color: var(--brand-strong);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font: 700 0.75rem/1.2 "Segoe UI", Tahoma, sans-serif;
    }}
    h1 {{
      margin: 0;
      max-width: 10ch;
      font-size: clamp(2.7rem, 5vw, 5rem);
      line-height: 0.9;
      font-weight: 700;
      letter-spacing: -0.04em;
    }}
    .lead {{
      max-width: 52ch;
      margin: 18px 0 0;
      color: var(--muted);
      font: 400 1.02rem/1.75 "Segoe UI", Tahoma, sans-serif;
    }}
    .meta-panel h3 {{
      margin: 0 0 12px;
      font-size: 1.15rem;
    }}
    .meta-panel p {{
      margin: 0 0 10px;
      color: var(--muted);
      font: 400 0.95rem/1.6 "Segoe UI", Tahoma, sans-serif;
    }}
    .meta-panel code {{
      font-family: Consolas, monospace;
      font-size: 0.9rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 18px;
    }}
    .card {{
      position: relative;
      overflow: hidden;
      padding: 22px;
      min-height: 260px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    }}
    .card:hover {{
      transform: translateY(-4px);
      box-shadow: 0 30px 70px rgba(22,35,59,0.14);
      border-color: rgba(17,94,89,0.18);
    }}
    .card::after {{
      content: "";
      position: absolute;
      right: -30px;
      bottom: -30px;
      width: 120px;
      height: 120px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(15,118,110,0.10), rgba(15,118,110,0));
      pointer-events: none;
    }}
    .orb {{
      width: 52px;
      height: 52px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 16px;
      margin-bottom: 22px;
      color: var(--ink);
      background: linear-gradient(135deg, rgba(15,118,110,0.18), rgba(217,119,6,0.12));
      border: 1px solid rgba(17,94,89,0.10);
      font: 700 1.1rem/1 "Segoe UI", Tahoma, sans-serif;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }}
    .card h2 {{
      margin: 0;
      font-size: 1.55rem;
      letter-spacing: -0.03em;
    }}
    .summary {{
      margin: 16px 0 20px;
      color: var(--muted);
      font: 400 0.96rem/1.68 "Segoe UI", Tahoma, sans-serif;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      white-space: nowrap;
      font: 700 0.74rem/1 "Segoe UI", Tahoma, sans-serif;
    }}
    .badge-live {{
      color: var(--brand-strong);
      background: var(--live-bg);
    }}
    .badge-missing {{
      color: var(--warning);
      background: var(--warning-bg);
    }}
    .cta {{
      display: inline-flex;
      width: fit-content;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 12px 18px;
      text-decoration: none;
      background: linear-gradient(135deg, var(--brand), var(--brand-strong));
      color: #fff;
      font: 700 0.92rem/1 "Segoe UI", Tahoma, sans-serif;
      box-shadow: 0 12px 24px rgba(15,118,110,0.20);
    }}
    .cta-disabled {{
      background: #e5e7eb;
      color: #6b7280;
      cursor: default;
      box-shadow: none;
    }}
    .footer {{
      margin-top: 18px;
      color: var(--muted);
      font: 400 0.9rem/1.6 "Segoe UI", Tahoma, sans-serif;
    }}
    @media (max-width: 860px) {{
      .hero {{
        grid-template-columns: 1fr;
      }}
      .wrap {{
        padding: 24px 16px 40px;
      }}
      .hero-panel,
      .meta-panel,
      .card {{
        border-radius: 22px;
      }}
      .hero-panel {{
        padding: 24px;
      }}
      h1 {{
        max-width: none;
      }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="hero-panel">
        <p class="eyebrow">Shared Entry Point</p>
        <h1>{escape(title)}</h1>
        <p class="lead">{escape(intro)}</p>
      </div>
      <aside class="meta-panel">
        <div>
          <h3>Configuration</h3>
          <p>Set each app URL as an environment variable on the Railway service.</p>
          <p><code>PORTAL_MARKETINGHUB_URL</code></p>
          <p><code>PORTAL_OWIS_URL</code></p>
          <p><code>PORTAL_OPPORTUNITIES_URL</code></p>
          <p><code>PORTAL_UMAMU_URL</code></p>
        </div>
        <p>Missing URLs are shown clearly so the landing page still works before everything is wired up.</p>
      </aside>
    </section>
    <section class="grid">
      {''.join(cards)}
    </section>
    <p class="footer">Deploy this as its own Railway service and use it as the canonical index for your app stack.</p>
  </main>
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
