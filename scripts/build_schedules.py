#!/usr/bin/env python3
"""Generate /schedules/ pages from seo/schedules.json (issue #19).

Idempotent: overwrites its 25 outputs (24 month pages + hub) on every run.

  seo/schedules.json  ->  schedules/{13..36}-month-old-schedule/index.html
                          schedules/index.html (hub)

Self-checks before writing (exit 1 on failure):
  - months are exactly 13..36, each with wake windows, naps, total sleep,
    sample day, what's changing and 4 FAQs (issue #19 data contract)
  - every <title> <= 60 chars and unique among generated pages
  - every generated meta description unique
  - every top answer paragraph 40-60 words
  - every JSON-LD block round-trips json.loads and has Article, FAQPage
    and BreadcrumbList nodes

Style/engine follows tools/sleep-milestone-calculator.html; CTA uses the
issue #19 UTM set (utm_source=marketing_site, utm_medium=cta, campaign=<slug>)
and the sticky mobile CTA from scripts/patch_sticky_mobile_cta.py.
"""

import html
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"
DATA = BASE / "seo" / "schedules.json"
MONTHS = list(range(13, 37))

ANALYTICS = """  <!-- Cloudflare Web Analytics -->
  <script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "b844caf1ba764318811b28d1942bbaef"}'></script>
  <!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-CLY78E6V4R"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-CLY78E6V4R');
  </script>
  <!-- MSFT Clarity -->
  <script type="text/javascript">
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "uawbuyagyv");
  </script>
"""

HEAD_STYLE = """  <link rel="preconnect" href="https://cdn.tailwindcss.com" crossorigin />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="icon" type="image/jpeg" href="/og/snugs-og.jpg" />
  <link rel="manifest" href="/site.webmanifest" />
  <meta name="theme-color" content="#EA580C" />
"""

TAILWIND_CONFIG = """  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            'display': ['"Crimson Pro"', 'Georgia', 'serif'],
            'sans': ['"DM Sans"', 'system-ui', 'sans-serif'],
          }
        }
      }
    }
  </script>
"""

PAGE_STYLE = """  <style>
    * { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
    body { font-family: 'DM Sans', system-ui, sans-serif; }
    @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes gradientShift { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
    .animate-fadeInUp { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; }
    .animate-fadeIn { animation: fadeIn 0.6s ease-out forwards; opacity: 0; }
    .delay-100 { animation-delay: 0.1s; }
    .glass-card { background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.8); }
    .soft-shadow { box-shadow: 0 2px 8px rgba(234, 88, 12, 0.04), 0 8px 24px rgba(234, 88, 12, 0.08), 0 16px 56px rgba(234, 88, 12, 0.08); }
    .gradient-warm { background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 25%, #fed7aa 50%, #ffedd5 75%, #fff7ed 100%); background-size: 400% 400%; animation: gradientShift 15s ease infinite; }
    .blob-decoration { position: absolute; mix-blend-mode: multiply; filter: blur(40px); opacity: 0.3; animation: blob 20s ease-in-out infinite; }
    @keyframes blob { 0%, 100% { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; transform: rotate(0deg) scale(1); } 50% { border-radius: 60% 40% 60% 30% / 70% 30% 60% 40%; transform: rotate(180deg) scale(1); } }
    /* Snugs sticky mobile CTA (#10): mobile-only, fixed, no CLS. Keep z-index 40 so cookie consent (50+) stays on top. */
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
  </style>
"""

# Sticky bar HTML (from scripts/patch_sticky_mobile_cta.py) — __CAMPAIGN__ replaced per page.
STICKY_TEMPLATE = """    <!-- Snugs sticky mobile CTA (#10): mobile-only via CSS, dismissible, reuses data-cta/cta_click (cta_id=sticky_mobile). Cookie consent should use z-index 50+. -->
    <div class="snugs-sticky-cta" id="snugs-sticky-cta" role="region" aria-label="Ask Snugs trial">
      <a href="https://app.snugs.ai/?utm_source=marketing_site&amp;utm_medium=cta&amp;utm_campaign=__CAMPAIGN__" data-cta="sticky_mobile" class="flex-1 inline-flex items-center justify-center px-5 py-3 bg-gradient-to-r from-orange-500 to-orange-600 text-white font-bold rounded-full hover:from-orange-600 hover:to-orange-700 transition-all shadow-lg text-sm">Ask Snugs &mdash; Start free trial</a>
      <button type="button" class="snugs-sticky-dismiss flex-shrink-0 w-9 h-9 rounded-full border border-orange-200 bg-white text-gray-600 font-bold leading-none" aria-label="Dismiss trial banner">&times;</button>
    </div>
    <script>
      (function() {
        var bar = document.getElementById('snugs-sticky-cta');
        if (!bar) return;
        try {
          if (sessionStorage.getItem('snugs_sticky_dismissed') === '1') {
            bar.setAttribute('hidden', '');
            document.body.classList.add('snugs-sticky-dismissed');
            return;
          }
        } catch (e) {}
        var btn = bar.querySelector('.snugs-sticky-dismiss');
        if (btn) {
          btn.addEventListener('click', function() {
            bar.setAttribute('hidden', '');
            document.body.classList.add('snugs-sticky-dismissed');
            try { sessionStorage.setItem('snugs_sticky_dismissed', '1'); } catch (e) {}
          });
        }
      })();
    </script>
"""

BINDER = """    <script>
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
    </script>
"""

FOOTER = """    <footer class="text-center pt-12 pb-8 text-gray-600">
      <p class="mb-4 text-base">&copy; 2026 Snugs.ai. Powered by AI, built with love</p>
      <div class="flex flex-wrap justify-center gap-6 text-sm">
        <a href="/" class="hover:text-orange-600 transition-colors font-medium">Home</a>
        <a href="/resources/" class="hover:text-orange-600 transition-colors font-medium">Resources</a>
        <a href="/tools/" class="hover:text-orange-600 transition-colors font-medium">Tools</a>
        <a href="/privacy.html" class="hover:text-orange-600 transition-colors font-medium">Privacy</a>
        <a href="/terms.html" class="hover:text-orange-600 transition-colors font-medium">Terms</a>
        <a href="/contact.html" class="hover:text-orange-600 transition-colors font-medium">Contact</a>
      </div>
      <div class="mt-6 flex flex-wrap justify-center items-center gap-3 sm:gap-4" data-badge-row="footer">
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
      </div>
    </footer>
"""

DAD_BOX = """      <aside class="rounded-3xl border border-orange-200 bg-orange-50/80 p-6" aria-label="About the author">
        <p class="font-semibold text-gray-800">Written by a dad</p>
        <p class="text-gray-700 mt-2">From the founder of Snugs.ai, a dad of a toddler building an AI parenting advisor for parents of 0-3 year olds.</p>
      </aside>
"""

SOURCES_NOTE = ("Sources: American Academy of Pediatrics (AAP) and CDC sleep guidance for toddlers, "
                "plus National Sleep Foundation (NSF) ranges for children aged 1&ndash;3. "
                "<strong>Not medical advice</strong> &mdash; these are typical ranges, not targets. "
                "If you have questions about your child&rsquo;s sleep or development, ask your pediatrician.")


def regression_for(month: int) -> str:
    """Must mirror scripts/verify_batch1.py regression_for()."""
    if month <= 15:
        return "12-month-sleep-regression"
    if month <= 23:
        return "18-month-sleep-regression"
    return "2-year-sleep-regression"


def title_for(month: int) -> str:
    return f"{month}-Month-Old Sleep Schedule: Naps, Wake Windows, Bedtime"


def desc_for(month: int) -> str:
    return (f"A {month}-month-old sleep schedule: sample wake, nap and bedtime times, wake "
            f"windows, total sleep, what changes at {month} months, plus 4 common questions answered.")


def h1_for(month: int) -> str:
    return f"{month}-Month-Old Sleep Schedule"


def answer_for(month: int, d: dict) -> str:
    a = d["answer"]
    return (f"Here is a realistic day for a {month}-month-old: wake up around {a['wake']}, "
            f"{a['naps_phrase']}, then bedtime around {a['bed']}. Wake windows run {a['ww']}, "
            f"and total sleep lands near {a['total']}. Shift any time 15 to 30 minutes to fit "
            f"your family, consistency beats the exact minute.")


def word_count(fragment: str) -> int:
    return len(html.unescape(fragment).split())


def jsonld_month(month: int, d: dict) -> str:
    url = f"{SITE}/schedules/{month}-month-old-schedule/"
    title, desc = title_for(month), desc_for(month)
    graph = [
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Schedules", "item": f"{SITE}/schedules/"},
                {"@type": "ListItem", "position": 3, "name": h1_for(month), "item": url},
            ],
        },
        {
            "@type": "Article",
            "headline": title,
            "description": desc,
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "author": {"@type": "Organization", "name": "Snugs.ai"},
            "publisher": {
                "@type": "Organization",
                "name": "Snugs.ai",
                "logo": {"@type": "ImageObject", "url": f"{SITE}/og/snugs-og.jpg"},
                "url": SITE,
            },
            "image": f"{SITE}/og/snugs-og.jpg",
            "datePublished": "2026-10-19",
            "dateModified": "2026-10-19",
        },
        {
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in d["faqs"]
            ],
        },
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2)


def jsonld_hub() -> str:
    url = f"{SITE}/schedules/"
    faqs = [
        ("How do I use these schedules?",
         "Find your child's month, copy the sample day as a skeleton, then move every time by "
         "15–30 minutes to fit your family. Consistency matters more than the exact clock time."),
        ("Which sleep ranges are these based on?",
         "They follow AAP, CDC and National Sleep Foundation sleep guidance for toddlers — 11–14 "
         "hours a day through age 2, then 10–13 — combined with common wake-window patterns of "
         "about 3 hours at 13 months stretching to about 6 hours by 36 months."),
        ("What if my child's schedule doesn't match?",
         "Every child is different, so treat these pages as starting points, not targets. If you "
         "have questions about your child's sleep or growth, ask your pediatrician."),
        ("Where can I calculate nap and bedtime times?",
         "The free wake window calculator turns your child's age and wake-up time into nap times "
         "and a bedtime, and the nap transition checker tells you when a nap drop is likely."),
    ]
    graph = [
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Schedules", "item": url},
            ],
        },
        {
            "@type": "Article",
            "headline": "Baby & Toddler Sleep Schedules by Month",
            "description": "24 monthly sleep schedules for ages 13–36 months with sample days, wake "
                           "windows, nap counts, total sleep and what changes each month.",
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "author": {"@type": "Organization", "name": "Snugs.ai"},
            "publisher": {
                "@type": "Organization",
                "name": "Snugs.ai",
                "logo": {"@type": "ImageObject", "url": f"{SITE}/og/snugs-og.jpg"},
                "url": SITE,
            },
            "image": f"{SITE}/og/snugs-og.jpg",
            "datePublished": "2026-10-19",
            "dateModified": "2026-10-19",
        },
        {
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faqs
            ],
        },
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2)


def cta_aside(slug: str, pitch: str) -> str:
    return f"""    <aside class="mt-10 text-center" aria-label="Start a free trial">
      <p class="text-gray-700 mb-4">{pitch}</p>
      <a id="cta-trial" href="https://app.snugs.ai/?utm_source=marketing_site&amp;utm_medium=cta&amp;utm_campaign={slug}" data-cta="{slug}" class="inline-flex items-center justify-center px-8 py-4 bg-gradient-to-r from-orange-500 to-orange-600 text-white font-bold rounded-full hover:from-orange-600 hover:to-orange-700 transition-all shadow-lg">Start your 14-day free trial</a>
    </aside>
"""


def month_page(month: int, d: dict, prev_m: int | None, next_m: int | None) -> str:
    slug = f"{month}-month-old-schedule"
    title, desc, h1 = title_for(month), desc_for(month), h1_for(month)
    answer = answer_for(month, d)
    reg = regression_for(month)
    canonical = f"{SITE}/schedules/{slug}/"

    rows = ""
    for r in d["sample_day"]:
        note_html = f'<p class="text-xs text-gray-500">{r["note"]}</p>' if r["note"] else ""
        rows += f"""          <div class="flex items-center gap-4 px-5 py-4">
            <div class="flex-1">
              <p class="font-semibold text-gray-800">{r["event"]}</p>
              {note_html}
            </div>
            <p class="font-bold text-orange-700 whitespace-nowrap max-md:whitespace-normal max-md:text-right max-md:text-sm">{r["time"]}</p>
          </div>
"""

    faqs = ""
    for f in d["faqs"]:
        faqs += f"""          <div>
            <dt class="font-semibold text-gray-800">{html.escape(f["q"])}</dt>
            <dd class="mt-1 text-gray-700">{html.escape(f["a"])}</dd>
          </div>
"""

    nav_mid = f'<a href="/schedules/" class="hover:text-orange-700 transition-colors font-medium">Schedules</a>\n      <span class="mx-2">&middot;</span>\n      '
    prev_html, next_html = "", ""
    if prev_m:
        prev_html = f'<li><a href="/schedules/{prev_m}-month-old-schedule/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">&larr; {prev_m}-month-old schedule</a></li>\n        '
    if next_m:
        next_html = f'<li><a href="/schedules/{next_m}-month-old-schedule/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">{next_m}-month-old schedule &rarr;</a></li>\n        '

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
{ANALYTICS}  <title>{title}</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{SITE}/og/snugs-og.jpg" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{desc}" />
  <meta name="twitter:image" content="{SITE}/og/snugs-og.jpg" />
{HEAD_STYLE}  <script type="application/ld+json">
{jsonld_month(month, d)}
  </script>
{TAILWIND_CONFIG}{PAGE_STYLE}</head>
<body class="gradient-warm min-h-screen overflow-x-hidden relative">
  <div class="blob-decoration w-80 h-80 bg-orange-400 rounded-full" style="top: -10%; right: -5%; animation-delay: 0s;"></div>
  <div class="blob-decoration w-64 h-64 bg-orange-300 rounded-full" style="bottom: 10%; left: -8%; animation-delay: 5s;"></div>

  <div class="container mx-auto px-4 py-8 md:py-16 max-w-3xl relative z-10">
    <nav class="text-sm text-gray-600 mb-6 animate-fadeIn" aria-label="Breadcrumb">
      <a href="/" class="hover:text-orange-700 transition-colors font-medium">Home</a>
      <span class="mx-2">&middot;</span>
      {nav_mid}<span class="text-gray-800">{h1}</span>
    </nav>

    <article class="glass-card rounded-[3rem] soft-shadow p-8 md:p-12 animate-fadeInUp delay-100">
      <header class="mb-6 text-center">
        <span class="inline-block px-4 py-1.5 bg-orange-100 text-orange-700 text-xs font-semibold tracking-widest uppercase rounded-full mb-4">Monthly schedule &middot; {month} months</span>
        <h1 class="text-3xl md:text-4xl font-display font-bold text-gray-800 mb-1">{h1}</h1>
      </header>

      <p class="text-gray-700 leading-relaxed mb-3 text-center">{answer}</p>
      <p class="text-gray-600 text-sm text-center mb-8">Not medical advice. Typical ranges, not targets &mdash; ask your pediatrician about your child.</p>

      <section class="mb-10" aria-label="Sample day">
        <h2 class="text-xl font-display font-bold text-gray-800 mb-4">A sample day for a {month}-month-old</h2>
        <div class="rounded-3xl border border-orange-200 bg-white/80 overflow-hidden soft-shadow mb-4">
          <div class="grid grid-cols-1 divide-y divide-orange-100">
{rows}          </div>
        </div>
        <div class="flex flex-wrap gap-3 text-sm">
          <div class="px-4 py-2 rounded-full bg-orange-50 border border-orange-200 text-orange-800 font-semibold">Wake windows: {d["wake_windows"]}</div>
          <div class="px-4 py-2 rounded-full bg-orange-50 border border-orange-200 text-gray-700">{d["naps"]}</div>
          <div class="px-4 py-2 rounded-full bg-orange-50 border border-orange-200 text-gray-700">{d["total_sleep"]}</div>
        </div>
      </section>

      <section class="mb-10" aria-label="What's changing">
        <h2 class="text-xl font-display font-bold text-gray-800 mb-3">What&rsquo;s changing at {month} months</h2>
        <p class="text-gray-700 leading-relaxed">{d["whats_changing"]}</p>
      </section>

      <section class="mb-10" aria-label="Frequently asked questions">
        <h2 class="text-xl font-display font-bold text-gray-800 mb-4">Frequently asked questions</h2>
        <dl class="space-y-4">
{faqs}        </dl>
      </section>

      <p class="text-xs text-gray-500 mb-6">{SOURCES_NOTE}</p>

{DAD_BOX}    </article>

{cta_aside(slug, "Want a schedule tuned to <em>your</em> kid? Ask Snugs builds one around their wake windows &mdash; free for 14 days.")}
    <aside class="mt-6 text-center" aria-label="Related schedules and tools">
      <p class="text-sm font-semibold text-gray-700 mb-3">Keep going</p>
      <ul class="text-sm space-y-2">
        {prev_html}{next_html}<li><a href="/schedules/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">All monthly schedules</a></li>
        <li><a href="/sleep-regressions/{reg}/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">The {reg.replace("-", " ")} explained</a></li>
        <li><a href="/sleep-regressions/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">All sleep regressions by age</a></li>
        <li><a href="/tools/wake-window-calculator/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">Wake window calculator</a></li>
        <li><a href="/tools/nap-transition-checker/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">Nap transition checker</a></li>
      </ul>
    </aside>

{STICKY_TEMPLATE.replace("__CAMPAIGN__", slug)}
{BINDER}{FOOTER}  </div>
</body>
</html>
"""


def hub_page(months: list[dict]) -> str:
    title = "Baby & Toddler Sleep Schedules by Month (13–36 Months)"
    desc = ("Baby and toddler sleep schedules by month for ages 13–36 months: sample days, wake "
            "windows, nap counts, total sleep ranges and what changes each month.")
    answer = ("Pick your child's month for a sample day built from typical wake windows, nap length "
              "and bedtime for that age: 24 schedules from 13 to 36 months, each with what changes, "
              "total sleep ranges and four answered questions. Use them as a starting point and "
              "shift times 15 to 30 minutes to fit your family.")
    canonical = f"{SITE}/schedules/"

    items = ""
    for d in months:
        m = d["month"]
        items += f"""        <li><a href="/schedules/{m}-month-old-schedule/" class="flex items-center justify-between gap-4 px-5 py-4 hover:bg-orange-50 transition-colors group">
          <span class="font-semibold text-gray-800 group-hover:text-orange-700">{m}-month-old schedule</span>
          <span class="text-xs text-gray-500 text-right">{d["wake_windows"]} awake &middot; {d["naps"]}</span>
        </a></li>
"""

    faq_vis = """
          <div>
            <dt class="font-semibold text-gray-800">How do I use these schedules?</dt>
            <dd class="mt-1 text-gray-700">Find your child's month, copy the sample day as a skeleton, then move every time by 15&ndash;30 minutes to fit your family. Consistency matters more than the exact clock time.</dd>
          </div>
          <div>
            <dt class="font-semibold text-gray-800">Which sleep ranges are these based on?</dt>
            <dd class="mt-1 text-gray-700">They follow AAP, CDC and National Sleep Foundation sleep guidance for toddlers &mdash; 11&ndash;14 hours a day through age 2, then 10&ndash;13 &mdash; combined with common wake-window patterns of about 3 hours at 13 months stretching to about 6 hours by 36 months.</dd>
          </div>
          <div>
            <dt class="font-semibold text-gray-800">What if my child's schedule doesn't match?</dt>
            <dd class="mt-1 text-gray-700">Every child is different, so treat these pages as starting points, not targets. If you have questions about your child's sleep or growth, ask your pediatrician.</dd>
          </div>
          <div>
            <dt class="font-semibold text-gray-800">Where can I calculate nap and bedtime times?</dt>
            <dd class="mt-1 text-gray-700">The free <a href="/tools/wake-window-calculator/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">wake window calculator</a> turns your child's age and wake-up time into nap times and a bedtime, and the <a href="/tools/nap-transition-checker/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">nap transition checker</a> tells you when a nap drop is likely.</dd>
          </div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
{ANALYTICS}  <title>{title}</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{SITE}/og/snugs-og.jpg" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{desc}" />
  <meta name="twitter:image" content="{SITE}/og/snugs-og.jpg" />
{HEAD_STYLE}  <script type="application/ld+json">
{jsonld_hub()}
  </script>
{TAILWIND_CONFIG}{PAGE_STYLE}</head>
<body class="gradient-warm min-h-screen overflow-x-hidden relative">
  <div class="blob-decoration w-80 h-80 bg-orange-400 rounded-full" style="top: -10%; right: -5%; animation-delay: 0s;"></div>
  <div class="blob-decoration w-64 h-64 bg-orange-300 rounded-full" style="bottom: 10%; left: -8%; animation-delay: 5s;"></div>

  <div class="container mx-auto px-4 py-8 md:py-16 max-w-3xl relative z-10">
    <nav class="text-sm text-gray-600 mb-6 animate-fadeIn" aria-label="Breadcrumb">
      <a href="/" class="hover:text-orange-700 transition-colors font-medium">Home</a>
      <span class="mx-2">&middot;</span>
      <span class="text-gray-800">Schedules</span>
    </nav>

    <article class="glass-card rounded-[3rem] soft-shadow p-8 md:p-12 animate-fadeInUp delay-100">
      <header class="mb-6 text-center">
        <span class="inline-block px-4 py-1.5 bg-orange-100 text-orange-700 text-xs font-semibold tracking-widest uppercase rounded-full mb-4">Free guides &middot; 13&ndash;36 months</span>
        <h1 class="text-3xl md:text-4xl font-display font-bold text-gray-800 mb-1">Baby &amp; Toddler Sleep Schedules by Month</h1>
      </header>

      <p class="text-gray-700 leading-relaxed mb-3 text-center">{answer}</p>
      <p class="text-gray-600 text-sm text-center mb-8">Not medical advice. Typical ranges, not targets &mdash; ask your pediatrician about your child.</p>

      <section class="mb-10" aria-label="Schedules by month">
        <h2 class="text-xl font-display font-bold text-gray-800 mb-4">Pick a month</h2>
        <div class="rounded-3xl border border-orange-200 bg-white/80 overflow-hidden soft-shadow">
          <ul class="divide-y divide-orange-100">
{items}          </ul>
        </div>
      </section>

      <section class="mb-10" aria-label="Frequently asked questions">
        <h2 class="text-xl font-display font-bold text-gray-800 mb-4">Frequently asked questions</h2>
        <dl class="space-y-4">
{faq_vis}        </dl>
      </section>

      <p class="text-xs text-gray-500 mb-6">{SOURCES_NOTE}</p>

{DAD_BOX}    </article>

{cta_aside("schedules", "Want a schedule tuned to <em>your</em> kid? Ask Snugs builds one around their wake windows &mdash; free for 14 days.")}
    <aside class="mt-6 text-center" aria-label="Free tools">
      <p class="text-sm font-semibold text-gray-700 mb-3">Free tools</p>
      <ul class="text-sm space-y-2">
        <li><a href="/tools/wake-window-calculator/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">Wake window calculator</a></li>
        <li><a href="/tools/nap-transition-checker/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">Nap transition checker</a></li>
        <li><a href="/sleep-regressions/" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">Sleep regressions by age</a></li>
      </ul>
    </aside>

{BINDER}{FOOTER}  </div>
</body>
</html>
"""


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    months = data["months"]
    got = [d["month"] for d in months]
    if got != MONTHS:
        print(f"FAIL: months are {got}, want exactly 13..36")
        return 1

    errors: list[str] = []
    titles: dict[str, int] = {}
    descs: dict[str, int] = {}

    for d in months:
        m = d["month"]
        for key in ("wake_windows", "naps", "total_sleep", "whats_changing"):
            if not d.get(key):
                errors.append(f"{m}mo: missing {key}")
        if len(d.get("sample_day", [])) < 3:
            errors.append(f"{m}mo: sample_day needs wake + nap + bedtime")
        if len(d.get("faqs", [])) != 4:
            errors.append(f"{m}mo: needs exactly 4 FAQs, has {len(d.get('faqs', []))}")
        t, desc = title_for(m), desc_for(m)
        if len(t) > 60:
            errors.append(f"{m}mo: title {len(t)} chars > 60: {t}")
        if t in titles:
            errors.append(f"{m}mo: duplicate title (also {titles[t]})")
        if desc in descs:
            errors.append(f"{m}mo: duplicate description (also {descs[desc]})")
        titles[t], descs[desc] = m, m
        n = word_count(answer_for(m, d))
        if not 40 <= n <= 60:
            errors.append(f"{m}mo: answer has {n} words, want 40-60")
        try:
            json.loads(jsonld_month(m, d))
        except json.JSONDecodeError as e:
            errors.append(f"{m}mo: JSON-LD invalid: {e}")

    hub_title = "Baby & Toddler Sleep Schedules by Month (13–36 Months)"
    if len(hub_title) > 60:
        errors.append(f"hub: title {len(hub_title)} chars > 60")
    if hub_title in titles:
        errors.append("hub: duplicate title")
    if not 40 <= word_count(
        "Pick your child's month for a sample day built from typical wake windows, nap length "
        "and bedtime for that age: 24 schedules from 13 to 36 months, each with what changes, "
        "total sleep ranges and four answered questions. Use them as a starting point and "
        "shift times 15 to 30 minutes to fit your family."
    ) <= 60:
        errors.append("hub: answer not 40-60 words")
    try:
        json.loads(jsonld_hub())
    except json.JSONDecodeError as e:
        errors.append(f"hub: JSON-LD invalid: {e}")

    if errors:
        print("DATA CONTRACT FAILURES:")
        for e in errors:
            print(" -", e)
        return 1

    written = 0
    for i, d in enumerate(months):
        m = d["month"]
        prev_m = months[i - 1]["month"] if i > 0 else None
        next_m = months[i + 1]["month"] if i + 1 < len(months) else None
        out = BASE / "schedules" / f"{m}-month-old-schedule" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(month_page(m, d, prev_m, next_m), encoding="utf-8")
        written += 1

    hub = BASE / "schedules" / "index.html"
    hub.parent.mkdir(parents=True, exist_ok=True)
    hub.write_text(hub_page(months), encoding="utf-8")
    written += 1

    print(f"schedules.json: {len(months)} months validated (titles, answers, FAQs, JSON-LD OK)")
    print(f"written: {written} files (24 month pages + hub)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
