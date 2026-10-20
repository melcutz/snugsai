#!/usr/bin/env python3
"""Shared page shell for SEO batch 1 (issue #19) generators.

build_schedules.py and build_regressions.py both render static pages with
the same head/style/footer/CTA/sticky machinery as the existing site:
Google Analytics cta_click binder, sticky mobile CTA (#10), footer badges,
self canonical, and @graph JSON-LD.
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"

NOT_MEDICAL = "Not medical advice. For emergencies, call your local emergency number."

SOURCES_LINE = (
    "Ranges follow the American Academy of Pediatrics (AAP) and CDC sleep "
    "guidance and National Sleep Foundation (NSF) totals for infants and "
    "toddlers."
)

DAD_BOX = """      <aside class="mt-10 rounded-3xl border border-orange-200 bg-orange-50/80 p-6" aria-label="About the author">
        <p class="font-semibold text-gray-800">Written by a dad</p>
        <p class="text-gray-700 mt-2">From the founder of Snugs.ai, a dad of a toddler building an AI parenting advisor for parents of 0-3 year olds.</p>
      </aside>"""

BADGES = """      <div class="mt-6 flex flex-wrap justify-center items-center gap-3 sm:gap-4" data-badge-row="footer">
        <div class="flex justify-center w-40 sm:w-auto" data-badge="aiagentsdirectory">
          <a href="https://aiagentsdirectory.com/agent/snugsai?utm_source=badge&amp;utm_medium=referral&amp;utm_campaign=free_listing&amp;utm_content=snugsai" target="_blank" rel="noopener noreferrer">
            <img src="https://aiagentsdirectory.com/featured-badge.svg?v=2024" alt="Snugs.ai - Featured on AI Agents Directory" width="200" height="50" class="h-auto max-w-full" loading="lazy" decoding="async" />
          </a>
        </div>
        <div class="flex justify-center w-40 sm:w-auto" data-badge="publishyoursaas">
          <a href="https://publishyoursaas.com" target="_blank" rel="noopener noreferrer">
            <img src="https://publishyoursaas.com/publishyoursaas-badge.svg" alt="Snugs.ai - Listed on PublishYourSaaS" width="200" height="50" class="h-auto max-w-full" loading="lazy" decoding="async" />
          </a>
        </div>
      </div>"""

STICKY_CSS = """    /* Snugs sticky mobile CTA (#10): mobile-only, fixed, no CLS. Keep z-index 40 so cookie consent (50+) stays on top. */
    .snugs-sticky-cta { display: none; }
    @media (max-width: 767px) {
      body { padding-bottom: calc(76px + env(safe-area-inset-bottom, 0px)); }
      body.snugs-sticky-dismissed { padding-bottom: 0; }
      .snugs-sticky-cta {
        display: flex;
        position: fixed;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 40;
        align-items: center;
        gap: 10px;
        padding: 10px 12px calc(10px + env(safe-area-inset-bottom, 0px));
        background: rgba(255, 255, 255, 0.96);
        border-top: 1px solid #fed7aa;
        box-shadow: 0 -8px 24px rgba(234, 88, 12, 0.12);
      }
      .snugs-sticky-cta[hidden] { display: none; }
    }
    @media (min-width: 768px) {
      .snugs-sticky-cta { display: none !important; }
    }
"""

BASE_CSS = """    * {
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    body {
      font-family: 'DM Sans', system-ui, sans-serif;
    }

    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(30px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    @keyframes blob {
      0%, 100% {
        border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%;
        transform: rotate(0deg) scale(1);
      }
      25% {
        border-radius: 30% 60% 70% 40% / 50% 60% 30% 60%;
        transform: rotate(90deg) scale(1.05);
      }
      50% {
        border-radius: 50% 60% 30% 60% / 30% 50% 70% 30%;
        transform: rotate(180deg) scale(1);
      }
      75% {
        border-radius: 60% 40% 60% 30% / 70% 30% 60% 40%;
        transform: rotate(270deg) scale(1.05);
      }
    }

    @keyframes gradientShift {
      0%, 100% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
    }

    .animate-fadeInUp {
      animation: fadeInUp 0.8s ease-out forwards;
      opacity: 0;
    }

    .animate-fadeIn {
      animation: fadeIn 0.6s ease-out forwards;
      opacity: 0;
    }

    .delay-100 { animation-delay: 0.1s; }
    .delay-200 { animation-delay: 0.2s; }

    .glass-card {
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.8);
    }

    .soft-shadow {
      box-shadow:
        0 2px 8px rgba(234, 88, 12, 0.04),
        0 8px 24px rgba(234, 88, 12, 0.08),
        0 16px 56px rgba(234, 88, 12, 0.08);
    }

    .gradient-warm {
      background: linear-gradient(135deg,
        #fff7ed 0%,
        #ffedd5 25%,
        #fed7aa 50%,
        #ffedd5 75%,
        #fff7ed 100%);
      background-size: 400% 400%;
      animation: gradientShift 15s ease infinite;
    }

    .blob-decoration {
      position: absolute;
      mix-blend-mode: multiply;
      filter: blur(40px);
      opacity: 0.3;
      animation: blob 20s ease-in-out infinite;
    }
"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def cta_url(slug: str) -> str:
    return (
        "https://app.snugs.ai/?utm_source=snugs.ai&amp;utm_medium=seo"
        f"&amp;utm_campaign={slug}"
    )


def ld_script(nodes: list) -> str:
    data = {"@context": "https://schema.org", "@graph": nodes}
    body = json.dumps(data, ensure_ascii=False, indent=2)
    body = re.sub(r"^", "  ", body, flags=re.M)
    return f'<script type="application/ld+json">\n{body}\n  </script>'


def breadcrumb_node(items: list[tuple[str, str]]) -> dict:
    """items: [(name, url), ...] including the page itself last."""
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": url,
            }
            for i, (name, url) in enumerate(items)
        ],
    }


def article_node(headline: str, description: str, url: str, date: str = "2026-10-19") -> dict:
    return {
        "@type": "Article",
        "headline": headline,
        "description": description,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "author": {"@type": "Organization", "name": "Snugs.ai"},
        "publisher": {
            "@type": "Organization",
            "name": "Snugs.ai",
            "logo": {"@type": "ImageObject", "url": f"{SITE}/og/snugs-og.jpg"},
            "url": SITE,
        },
        "image": f"{SITE}/og/snugs-og.jpg",
        "datePublished": date,
        "dateModified": date,
    }


def faq_node(faqs: list[dict]) -> dict:
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f["q"],
                "acceptedAnswer": {"@type": "Answer", "text": f["a"]},
            }
            for f in faqs
        ],
    }


def software_node(name: str, description: str, url: str) -> dict:
    return {
        "@type": "SoftwareApplication",
        "name": name,
        "applicationCategory": "HealthApplication",
        "operatingSystem": "Any",
        "description": description,
        "url": url,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }


def collection_node(name: str, description: str, url: str) -> dict:
    return {
        "@type": "CollectionPage",
        "name": name,
        "description": description,
        "url": url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }


def nav_html(crumbs: list[tuple[str, str | None]]) -> str:
    parts = []
    for i, (name, href) in enumerate(crumbs):
        if href:
            parts.append(f'<a href="{href}" class="hover:text-orange-700 transition-colors font-medium">{esc(name)}</a>')
        else:
            parts.append(f'<span class="text-gray-800">{esc(name)}</span>')
        if i < len(crumbs) - 1:
            parts.append('<span class="mx-2">·</span>')
    return (
        '    <nav class="text-sm text-gray-600 mb-6 animate-fadeIn" aria-label="Breadcrumb">\n'
        "      " + "\n      ".join(parts) + "\n    </nav>"
    )


def cta_html(slug: str) -> str:
    return f"""      <aside class="mt-10 text-center" aria-label="Start a free trial">
        <p class="text-gray-700 mb-4">Get a schedule tuned to <em>your</em> kid. Ask Snugs, free for 14 days.</p>
        <a id="cta-trial" href="{cta_url(slug)}" data-cta="{slug}" class="inline-flex items-center justify-center px-8 py-4 bg-gradient-to-r from-orange-500 to-orange-600 text-white font-bold rounded-full hover:from-orange-600 hover:to-orange-700 transition-all shadow-lg">Start your 14-day free trial</a>
      </aside>"""


STICKY_HTML = """    <!-- Snugs sticky mobile CTA (#10): mobile-only via CSS, dismissible, reuses data-cta/cta_click (cta_id=sticky_mobile). Cookie consent should use z-index 50+. -->
    <div class="snugs-sticky-cta" id="snugs-sticky-cta" role="region" aria-label="Ask Snugs trial">
      <a href="{cta}" data-cta="sticky_mobile" class="flex-1 inline-flex items-center justify-center px-5 py-3 bg-gradient-to-r from-orange-500 to-orange-600 text-white font-bold rounded-full hover:from-orange-600 hover:to-orange-700 transition-all shadow-lg text-sm">Ask Snugs &mdash; Start free trial</a>
      <button type="button" class="snugs-sticky-dismiss flex-shrink-0 w-9 h-9 rounded-full border border-orange-200 bg-white text-gray-600 font-bold leading-none" aria-label="Dismiss trial banner">&times;</button>
    </div>
    <script>
      (function() {{
        var bar = document.getElementById('snugs-sticky-cta');
        if (!bar) return;
        try {{
          if (sessionStorage.getItem('snugs_sticky_dismissed') === '1') {{
            bar.setAttribute('hidden', '');
            document.body.classList.add('snugs-sticky-dismissed');
            return;
          }}
        }} catch (e) {{}}
        var btn = bar.querySelector('.snugs-sticky-dismiss');
        if (btn) {{
          btn.addEventListener('click', function() {{
            bar.setAttribute('hidden', '');
            document.body.classList.add('snugs-sticky-dismissed');
            try {{ sessionStorage.setItem('snugs_sticky_dismissed', '1'); }} catch (e) {{}}
          }});
        }}
      }})();
    </script>
"""

BINDER_SCRIPT = """    <script>
      document.querySelectorAll('[data-cta]').forEach(function(el) {
        el.addEventListener('click', function() {
          if (typeof gtag === 'function') {
            gtag('event', 'cta_click', {
              cta_id: el.getAttribute('data-cta'),
              link_url: el.href,
              link_domain: (function(){ try { return new URL(el.href).hostname; } catch(e){ return 'unknown'; } })()
            });
          }
        });
      });
    </script>"""

FOOTER = """    <footer class="text-center pt-12 pb-8 text-gray-600">
      <p class="mb-4 text-base">© 2026 Snugs.ai. Powered by AI, built with love</p>
      <div class="flex flex-wrap justify-center gap-6 text-sm">
        <a href="/" class="hover:text-orange-600 transition-colors font-medium">Home</a>
        <a href="/resources/" class="hover:text-orange-600 transition-colors font-medium">Resources</a>
        <a href="/privacy.html" class="hover:text-orange-600 transition-colors font-medium">Privacy</a>
        <a href="/terms.html" class="hover:text-orange-600 transition-colors font-medium">Terms</a>
        <a href="/contact.html" class="hover:text-orange-600 transition-colors font-medium">Contact</a>
      </div>
{badges}
    </footer>""".format(badges=BADGES)


def head_block(
    title: str, description: str, canonical: str, ld_nodes: list, css_extra: str = ""
) -> str:
    ld = ld_script(ld_nodes)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />

  <!-- Cloudflare Web Analytics -->
  <script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "b844caf1ba764318811b28d1942bbaef"}}'></script>
  <!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-CLY78E6V4R"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-CLY78E6V4R');
  </script>
  <!-- MSFT Clarity -->
  <script type="text/javascript">
    (function(c,l,a,r,i,t,y){{
        c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    }})(window, document, "clarity", "script", "uawbuyagyv");
  </script>
  <title>{title}</title>
  <meta name="description" content="{esc(description)}" />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{SITE}/og/snugs-og.jpg" />
  <meta property="og:image:width" content="1000" />
  <meta property="og:image:height" content="1500" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{esc(title)}" />
  <meta name="twitter:description" content="{esc(description)}" />
  <meta name="twitter:image" content="{SITE}/og/snugs-og.jpg" />
  <link rel="preconnect" href="https://cdn.tailwindcss.com" crossorigin />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="icon" type="image/jpeg" href="/og/snugs-og.jpg" />
  <link rel="manifest" href="/site.webmanifest" />
  <meta name="theme-color" content="#EA580C" />
  {ld}
  <script>
    tailwind.config = {{
      theme: {{
        extend: {{
          fontFamily: {{
            'display': ['"Crimson Pro"', 'Georgia', 'serif'],
            'sans': ['"DM Sans"', 'system-ui', 'sans-serif'],
          }}
        }}
      }}
    }}
  </script>
  <style>
{BASE_CSS}{css_extra}  </style>
</head>"""


def render_page(
    *,
    title: str,
    description: str,
    canonical: str,
    ld_nodes: list,
    crumbs: list[tuple[str, str | None]],
    body_main: str,
    slug: str,
    sticky: bool,
    extra_js: str = "",
) -> str:
    """Assemble a full page. body_main sits inside <article>."""
    css_extra = STICKY_CSS if sticky else ""
    sticky_block = STICKY_HTML.format(cta=cta_url(slug)) if sticky else ""
    return f"""{head_block(title, description, canonical, ld_nodes, css_extra)}
<body class="gradient-warm min-h-screen overflow-x-hidden relative">

  <!-- Decorative blobs -->
  <div class="blob-decoration w-80 h-80 bg-orange-400 rounded-full" style="top: -10%; right: -5%; animation-delay: 0s;"></div>
  <div class="blob-decoration w-64 h-64 bg-orange-300 rounded-full" style="bottom: 10%; left: -8%; animation-delay: 5s;"></div>

  <div class="container mx-auto px-4 py-8 md:py-16 max-w-3xl relative z-10">
{nav_html(crumbs)}

    <article class="glass-card rounded-[3rem] soft-shadow p-8 md:p-12 animate-fadeInUp delay-100">
{body_main}
    </article>

{sticky_block}{BINDER_SCRIPT}

{FOOTER}
  </div>
{extra_js}
</body>
</html>
"""


def answer_words(text_html: str) -> int:
    return len(strip_tags(text_html).split())


def strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment))


def check_answer(paragraph_html: str, where: str) -> None:
    n = answer_words(paragraph_html)
    if not 40 <= n <= 60:
        raise SystemExit(f"answer paragraph in {where} is {n} words (need 40-60)")
