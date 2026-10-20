#!/usr/bin/env python3
"""Generate topic hub pages for resources/ with AI Agents badge."""

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RESOURCES = BASE / "resources"

rows = list(csv.DictReader(open(BASE / "seo" / "classification.csv")))
keep_articles = [r for r in rows if r["decision"] == "keep"]

pregnancy = []
newborn = []
baby = []
toddler = []
dads = []

for article in keep_articles:
    slug = article["path"].replace("resources/", "").replace(".html", "")
    title = article["title"].split(" | ")[0]
    text = f"{slug} {title}".lower()
    
    if any(kw in text for kw in ["pregnan", "postpartum", "expecting", "childbirth", "labor", "delivery", "unplanned pregnancy", "new mom", "new dad", "new parent", "new fatherhood", "partner leave", "hospital stays during pregnancy"]):
        pregnancy.append((slug, title))
    elif any(kw in text for kw in ["newborn", "infant", "0-3", "week", "month-old", "weeks old", "months old", "swaddl", "colic", "grunting", "fussy baby", "crying baby", "baby bath", "baby fell", "baby safety", "breastfeed", "bottle", "formula", "milk intake", "pooping", "diaper", "rsv", "engaging your 3-month", "essential newborn", "keeping baby", "perianal", "post-delivery", "protecting your newborn", "safe swaddling", "screen time infant", "soothing a fussy", "surviving the newborn", "understanding baby", "unusual baby sleeping", "when to take your baby", "when your baby cries", "wheeled baby swings", "calm a crying"]):
        newborn.append((slug, title))
    elif any(kw in text for kw in ["baby", "9-month", "6-month", "12-month", "teething", "solids", "milk intake", "poop", "diaper", "nap", "sleep regression", "bedtime", "co-sleep", "contact naps", "mastering baby", "navigating baby", "helping your baby", "hunger vs tired", "is an 8-hour", "is your 3-month", "sudden sleep", "baby tooth", "having a big baby", "baby length", "baby not pooping"]):
        baby.append((slug, title))
    elif any(kw in text for kw in ["toddler", "2-year", "3-year", "18-month", "terrible two", "terrible three", "potty train", "tantrum", "aggression", "overstimulation", "independence", "visual routine", "milestone", "first birthday", "first word", "babble", "speech", "language", "talkers", "celebrating toddler", "cracking the toddler", "embrace the silly", "encouraging independent", "help your toddler sleep", "helping your child overcome", "how to get your 3-year", "managing aggressive", "navigating 2-2-3", "navigating aggression", "navigating cold weather", "navigating daycare", "navigating developmental", "navigating feeding fears", "navigating funerals", "navigating grief", "navigating the 18-month", "navigating the 2-year", "navigating the mine", "navigating the no phase", "navigating the storm", "navigating the terrible", "navigating toddler", "potty training", "preventing baby hair", "santa workshop", "sleep regression milestones", "surviving the toddler", "talking to young children", "the bittersweet", "the blowout", "the don't eat", "the joy of reading", "the math of parenthood", "the miraculous moment", "the most beloved lullabies", "the power of audio", "the power of movement", "three's a charm", "tips for safely cleaning", "toddler chaos", "toddler inhaled", "toddler pajamas", "toddler playtime", "toddler's adorable", "toddler snack", "toddler tantrums", "toddler tv", "toniebox vs yoto", "transitioning your toddler", "understanding and addressing", "understanding and managing", "understanding yes and no", "understanding your baby's temperament", "using timers", "when do toddlers", "when does a babble", "when kids pick up", "when love isn't enough", "when to rehome", "when toddlers lock", "why do kids act differently", "why is my preschooler"]):
        toddler.append((slug, title))
    elif any(kw in text for kw in ["dad", "father", "paternal", "dada tax", "hungry dad", "journey to fatherhood", "power of the dad network", "beyond sleep deprivation", "conquering the laundry", "navigating the chaos", "navigating new fatherhood", "navigating the dada", "navigating the golden fountain"]):
        dads.append((slug, title))
    else:
        toddler.append((slug, title))

for cat in [pregnancy, newborn, baby, toddler, dads]:
    cat.sort(key=lambda x: x[1])

def generate_hub(cat_name, articles, description):
    article_html = []
    for i, (slug, title) in enumerate(articles):
        delay = (i % 4) + 1
        delay_class = f"delay-{delay}00"
        article_html.append(f'''        <a
              href="/resources/{slug}.html"
              class="resource-card block rounded-3xl bg-white border-2 border-orange-100 p-8 soft-shadow hover:border-orange-200 focus:outline-none focus:ring-4 focus:ring-orange-300 cursor-pointer group animate-fadeInUp {delay_class}"
            >
              <div class="flex items-start gap-4 mb-4">
                <div
                  class="w-12 h-12 bg-gradient-to-br from-orange-600 to-orange-700 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg"
                >
                  <svg
                    class="w-6 h-6 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                    ></path>
                  </svg>
                </div>
                <div class="flex-1">
                  <h3 class="text-lg font-semibold text-gray-800 mb-2 group-hover:text-orange-700 transition-colors">{title}</h3>
                </div>
              </div>
              <div class="text-orange-700 text-sm font-medium flex items-center gap-2 group-hover:gap-3 transition-all">
                <span>Read Guide</span>
                <svg class="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
              </div>
            </a>''')
    articles_html = "\n".join(article_html)
    
    # Template with both badges in shared row container
    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "b844caf1ba764318811b28d1942bbaef"}}'></script>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-CLY78E6V4R"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-CLY78E6V4R');
  </script>
  <script type="text/javascript">
      (function(c,l,a,r,i,t,y){{
          c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
          t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
          y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
      }})(window, document, "clarity", "script", "uawbuyagyv");
  </script>
  <title>{cat_name.capitalize()} Resources | Snugs.ai</title>
  <meta name="description" content="{description}" />
  <link rel="canonical" href="https://snugs.ai/resources/{cat_name.lower()}/" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{cat_name.capitalize()} Resources | Snugs.ai" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="https://snugs.ai/resources/{cat_name.lower()}/" />
  <meta property="og:image" content="https://snugs.ai/og/snugs-og.jpg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{cat_name.capitalize()} Resources | Snugs.ai" />
  <meta name="twitter:description" content="{description}" />
  <meta name="twitter:image" content="https://snugs.ai/og/snugs-og.jpg" />
  <link rel="preconnect" href="https://cdn.tailwindcss.com" crossorigin>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="icon" type="image/jpeg" href="/og/snugs-og.jpg">
  <link rel="manifest" href="/site.webmanifest">
  <meta name="theme-color" content="#EA580C">
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
    * {{ -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
    body {{ font-family: 'DM Sans', system-ui, sans-serif; }}
    @keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(30px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes blob {{ 0%, 100% {{ border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; transform: rotate(0deg) scale(1); }} 25% {{ border-radius: 30% 60% 70% 40% / 50% 60% 30% 60%; transform: rotate(90deg) scale(1.05); }} 50% {{ border-radius: 50% 60% 30% 60% / 30% 50% 70% 40%; transform: rotate(180deg) scale(1); }} 75% {{ border-radius: 60% 40% 60% 30% / 70% 30% 60% 50%; transform: rotate(270deg) scale(1.05); }} }}
    @keyframes gradientShift {{ 0%, 100% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} }}
    .animate-fadeInUp {{ animation: fadeInUp 0.8s ease-out forwards; opacity: 0; }}
    .animate-fadeIn {{ animation: fadeIn 0.6s ease-out forwards; opacity: 0; }}
    .delay-100 {{ animation-delay: 0.1s; }} .delay-200 {{ animation-delay: 0.2s; }} .delay-300 {{ animation-delay: 0.3s; }} .delay-400 {{ animation-delay: 0.4s; }}
    .glass-card {{ background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.8); }}
    .soft-shadow {{ box-shadow: 0 2px 8px rgba(234, 88, 12, 0.04), 0 8px 24px rgba(234, 88, 12, 0.08), 0 16px 56px rgba(234, 88, 12, 0.08); }}
    .gradient-warm {{ background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 25%, #fed7aa 50%, #ffedd5 75%, #fff7ed 100%); background-size: 400% 400%; animation: gradientShift 15s ease infinite; }}
    .blob-decoration {{ position: absolute; mix-blend-mode: multiply; filter: blur(40px); opacity: 0.3; animation: blob 20s ease-in-out infinite; }}
    .resource-card {{ transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); }}
    .resource-card:hover {{ transform: translateY(-4px); }}
  </style>
</head>
<body class="gradient-warm min-h-screen overflow-x-hidden relative">
  <div class="blob-decoration w-96 h-96 bg-orange-400 rounded-full" style="top: -10%; right: -5%; animation-delay: 0s;"></div>
  <div class="blob-decoration w-80 h-80 bg-orange-300 rounded-full" style="bottom: 10%; left: -8%; animation-delay: 5s;"></div>
  <div class="container mx-auto px-4 py-8 md:py-16 max-w-6xl relative z-10">
    <header class="text-center mb-16 md:mb-20 animate-fadeIn">
      <a href="/" class="inline-block focus:outline-none focus:ring-4 focus:ring-orange-300 rounded">
        <h1 class="text-5xl md:text-7xl font-bold text-orange-600 mb-3 font-display">Snugs<span class="text-orange-500">.ai</span></h1>
      </a>
      <div class="h-1 w-32 bg-gradient-to-r from-transparent via-orange-400 to-transparent mx-auto mb-3"></div>
      <p class="text-orange-700 text-xs md:text-sm tracking-[0.3em] uppercase font-semibold">Parenting Resources</p>
    </header>
    <main class="animate-fadeInUp delay-100">
      <div class="glass-card rounded-[3rem] soft-shadow p-8 md:p-12 mb-8">
        <div class="rounded-2xl bg-orange-100 border-2 border-orange-200 text-orange-900 px-6 py-4 text-sm md:text-base mb-8 flex items-start gap-3" role="note">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="flex-shrink-0 mt-0.5">
            <circle cx="12" cy="12" r="10" stroke="#ea580c" stroke-width="2" fill="none"/>
            <path d="M12 8V12M12 16H12.01" stroke="#ea580c" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <span>Not medical advice. For emergencies call your local emergency number.</span>
        </div>
        <h2 class="text-3xl md:text-4xl font-display font-bold text-gray-800 mb-8">{cat_name.capitalize()} Guides</h2>
        <div class="grid md:grid-cols-2 gap-6">
{articles_html}
        </div>
      </div>
      <nav class="mt-10 text-center animate-fadeInUp delay-200" aria-label="Breadcrumb">
        <a href="/resources/" class="text-orange-700 hover:text-orange-800 underline text-sm font-medium">← Back to All Resources</a>
      </nav>
      <footer class="mt-16 mb-8 text-center text-gray-500 text-sm animate-fadeIn">
        <div class="mt-6 flex flex-wrap justify-center items-center gap-3 sm:gap-4" data-badge-row="footer">
          <div class="flex justify-center w-40 sm:w-auto" data-badge="aiagentsdirectory">
            <a href="https://aiagentsdirectory.com/agent/snugsai?utm_source=badge&utm_medium=referral&utm_campaign=free_listing&utm_content=snugsai" target="_blank" rel="noopener noreferrer">
              <img src="https://aiagentsdirectory.com/featured-badge.svg?v=2024" alt="Snugs.ai - Featured on AI Agents Directory" width="200" height="50" class="h-auto max-w-full" loading="lazy" decoding="async" />
            </a>
          </div>
          <div class="flex justify-center w-40 sm:w-auto" data-badge="publishyoursaas">
            <a href="https://publishyoursaas.com" target="_blank" rel="noopener noreferrer">
              <img src="https://publishyoursaas.com/publishyoursaas-badge.svg" alt="Snugs.ai - Listed on PublishYourSaaS" width="200" height="50" class="h-auto max-w-full" loading="lazy" decoding="async" />
            </a>
          </div>
        </div>
        <p>&copy; 2026 Snugs.ai. All rights reserved.</p>
        <p class="mt-2">
          <a href="/privacy.html" class="text-orange-700 hover:underline mx-2">Privacy</a>
          <a href="/terms.html" class="text-orange-700 hover:underline mx-2">Terms</a>
          <a href="/contact.html" class="text-orange-700 hover:underline mx-2">Contact</a>
        </p>
      </footer>
    </main>
  </div>
</body>
</html>"""
    return template

categories = [
    ("pregnancy", pregnancy, "Pregnancy guides for expecting parents. Expert advice on prenatal care, childbirth preparation, and the transition to parenthood."),
    ("newborn", newborn, "Newborn care guides for the first 3 months. Sleep, feeding, safety, and development tips for new parents."),
    ("baby", baby, "Baby guides for months 4-12. Sleep regressions, solid foods, motor milestones, and daily care."),
    ("toddler", toddler, "Toddler guides for ages 1-3. Behavior, potty training, sleep, language development, and activities."),
    ("dads", dads, "Guides for dads of young kids. Pregnancy support, newborn care, toddler parenting, and fatherhood journey."),
]

for cat_name, articles, desc in categories:
    cat_dir = RESOURCES / cat_name
    cat_dir.mkdir(exist_ok=True)
    content = generate_hub(cat_name, articles, desc)
    (cat_dir / "index.html").write_text(content, encoding="utf-8")
    print(f"Created {cat_dir}/index.html with {len(articles)} articles")

print(f"Category counts: pregnancy={len(pregnancy)}, newborn={len(newborn)}, baby={len(baby)}, toddler={len(toddler)}, dads={len(dads)}")
print(f"Total: {len(pregnancy) + len(newborn) + len(baby) + len(toddler) + len(dads)}")