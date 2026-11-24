import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

test("1. Mobile hero CTA appears above the fold in the initial hero section", () => {
  const indexPath = path.join(repoRoot, "index.html");
  const indexHtml = fs.readFileSync(indexPath, "utf-8");

  // Initial hero section check
  const heroMatch = indexHtml.match(/<!-- Hero Section -->([\s\S]*?)<!-- App Slides Showcase -->/);
  assert.ok(heroMatch, "Hero section markup must exist in index.html");
  const heroContent = heroMatch[1];

  // Mobile CTA exists within the hero
  assert.ok(
    heroContent.includes('data-cta="home-hero"'),
    "Hero CTA with data-cta='home-hero' must exist inside hero section"
  );

  // Assert mobile CTA comes immediately after the h2 headline
  const h2Pos = heroContent.indexOf("</h2>");
  assert.ok(h2Pos !== -1, "Hero headline h2 must exist");

  const mobileCtaPos = heroContent.indexOf("block lg:hidden");
  assert.ok(mobileCtaPos !== -1, "Mobile-specific CTA container must exist in hero");
  assert.ok(mobileCtaPos > h2Pos, "Mobile CTA must be located after the h2 headline");

  // Mobile CTA must appear BEFORE the long description paragraph
  const descParagraphPos = heroContent.indexOf("Meet Snugs, the AI parenting advisor");
  assert.ok(descParagraphPos !== -1, "Meet Snugs intro paragraph must exist");
  assert.ok(
    mobileCtaPos < descParagraphPos,
    "Mobile CTA must appear before the intro description paragraph to ensure above-the-fold visibility on 390px screens"
  );

  // Desktop CTA exists and is hidden on mobile
  assert.ok(
    heroContent.includes("hidden lg:block"),
    "Desktop CTA container must use hidden lg:block to avoid duplicate CTA clutter on mobile"
  );

  // Assert required UTM params on all hero CTA links
  const heroCtaMatches = heroContent.match(/href="([^"]+)"[^>]*data-cta="home-hero"/g) || [];
  assert.ok(heroCtaMatches.length >= 2, "Both mobile and desktop hero CTA links must carry data-cta='home-hero'");

  for (const match of heroCtaMatches) {
    assert.ok(match.includes("https://app.snugs.ai/?"), "Hero CTA must point to app.snugs.ai");
    assert.ok(match.includes("utm_source=marketing_site"), "Hero CTA must include utm_source=marketing_site");
    assert.ok(match.includes("utm_medium=cta"), "Hero CTA must include utm_medium=cta");
    assert.ok(match.includes("utm_campaign=home-hero"), "Hero CTA must include utm_campaign=home-hero");
  }

  // Sizing adjustments on mobile bear image
  assert.ok(
    heroContent.includes("w-40 h-40 sm:w-56 sm:h-56 lg:w-[400px] lg:h-[400px]"),
    "Bear illustration must be responsive and scaled down on small viewports"
  );
});

test("2. Public share image download control is not visible in homepage markup", () => {
  const indexPath = path.join(repoRoot, "index.html");
  const indexHtml = fs.readFileSync(indexPath, "utf-8");

  // Author/debug download button must be removed from public homepage
  assert.strictEqual(
    indexHtml.includes("Download share image"),
    false,
    "Homepage markup must not contain public 'Download share image' control"
  );
  assert.strictEqual(
    indexHtml.includes('download class="inline-flex items-center gap-3 rounded-full bg-orange-100 text-orange-700'),
    false,
    "Download share image anchor element must be removed"
  );

  // Verify social share buttons remain present and functional
  const requiredPlatforms = ["facebook", "reddit", "instagram", "tiktok", "whatsapp", "linkedin", "x"];
  for (const platform of requiredPlatforms) {
    assert.ok(
      indexHtml.includes(`data-platform="${platform}"`),
      `Social share button for ${platform} must remain present in markup`
    );
  }

  // Verify FAQ accordion markup is not regressed
  assert.ok(indexHtml.includes("<details class=\"group"), "FAQ accordions details elements must remain present");
  assert.ok(indexHtml.includes("<summary class=\"cursor-pointer"), "FAQ accordion summary elements must remain present");
});

test("3. Tool URLs and redirect stubs resolve with and without .html / trailing slash", () => {
  const staticRedirectMap = {
    "/tools/wake-window-calculator.html": "/tools/wake-window-calculator/",
    "/tools/sleep-milestone-calculator.html": "/tools/sleep-milestone-calculator/",
  };

  // Helper function to simulate URL resolution on static hosting
  function resolveUrl(urlPath) {
    const cleanPath = urlPath.split("?")[0].split("#")[0];
    const rel = cleanPath.replace(/^\//, "");

    // 1. Direct file check
    const directFile = path.join(repoRoot, rel);
    if (fs.existsSync(directFile) && fs.statSync(directFile).isFile()) {
      const content = fs.readFileSync(directFile, "utf-8");
      // Check if it is a meta-refresh redirect stub
      const refreshMatch = content.match(/<meta\s+http-equiv="refresh"\s+content="0;\s*url=([^"]+)"/i);
      if (refreshMatch) {
        return { status: 301, redirect: refreshMatch[1], file: rel };
      }
      return { status: 200, file: rel };
    }

    // 2. Directory index check (e.g. /tools/wake-window-calculator/ or /tools/wake-window-calculator)
    const dirPath = path.join(repoRoot, rel);
    if (fs.existsSync(dirPath) && fs.statSync(dirPath).isDirectory()) {
      const indexPath = path.join(dirPath, "index.html");
      if (fs.existsSync(indexPath)) {
        return { status: 200, file: path.join(rel, "index.html") };
      }
    }

    return { status: 404, file: rel };
  }

  // Assert canonical directory endpoints return 200
  const canonicalWakeWindow = resolveUrl("/tools/wake-window-calculator/");
  assert.strictEqual(canonicalWakeWindow.status, 200, "Canonical Wake Window directory must resolve to 200");
  assert.strictEqual(canonicalWakeWindow.file, "tools/wake-window-calculator/index.html");

  const canonicalSleepMilestone = resolveUrl("/tools/sleep-milestone-calculator/");
  assert.strictEqual(canonicalSleepMilestone.status, 200, "Canonical Sleep Milestone directory must resolve to 200");
  assert.strictEqual(canonicalSleepMilestone.file, "tools/sleep-milestone-calculator/index.html");

  // Assert URL without trailing slash normalizes to directory index (200)
  const normWakeWindow = resolveUrl("/tools/wake-window-calculator");
  assert.strictEqual(normWakeWindow.status, 200, "Wake Window URL without trailing slash must resolve");

  const normSleepMilestone = resolveUrl("/tools/sleep-milestone-calculator");
  assert.strictEqual(normSleepMilestone.status, 200, "Sleep Milestone URL without trailing slash must resolve");

  // Assert .html URLs redirect to canonical directory endpoints
  for (const [sourceUrl, targetUrl] of Object.entries(staticRedirectMap)) {
    const res = resolveUrl(sourceUrl);
    assert.strictEqual(res.status, 301, `${sourceUrl} must be a redirect stub`);
    assert.ok(
      res.redirect === targetUrl || res.redirect === `https://snugs.ai${targetUrl}`,
      `${sourceUrl} must redirect to ${targetUrl} (got ${res.redirect})`
    );

    // Verify stub contents
    const stubContent = fs.readFileSync(path.join(repoRoot, res.file), "utf-8");
    assert.ok(stubContent.includes('meta http-equiv="refresh"'), "Stub must contain meta refresh tag");
    assert.ok(stubContent.includes('rel="canonical"'), "Stub must contain canonical link tag");
    assert.ok(stubContent.includes('content="noindex'), "Stub must contain noindex meta tag");
    assert.ok(
      stubContent.includes(`href="${targetUrl}"`) || stubContent.includes(`href="https://snugs.ai${targetUrl}"`),
      "Stub must contain fallback visible link"
    );
    assert.ok(stubContent.includes("location.replace"), "Stub must use location.replace");
    assert.ok(stubContent.includes("location.search"), "Stub must preserve location.search");
    assert.ok(stubContent.includes("location.hash"), "Stub must preserve location.hash");
    assert.ok(
      stubContent.includes(`location.replace('${targetUrl}' + location.search + location.hash)`),
      `Stub must preserve search and hash targeting ${targetUrl}`
    );

    // Verify target of redirect exists and returns 200
    const targetRes = resolveUrl(targetUrl);
    assert.strictEqual(targetRes.status, 200, `Redirect target ${targetUrl} must return 200`);
  }
});

test("4. In-site links use canonical directory URLs without .html and do not 404", () => {
  function getAllHtmlFiles(dir) {
    const results = [];
    const list = fs.readdirSync(dir);
    for (const file of list) {
      if (file === ".git" || file === "node_modules") continue;
      const fullPath = path.join(dir, file);
      const stat = fs.statSync(fullPath);
      if (stat.isDirectory()) {
        results.push(...getAllHtmlFiles(fullPath));
      } else if (file.endsWith(".html")) {
        results.push(fullPath);
      }
    }
    return results;
  }

  const allHtmlFiles = getAllHtmlFiles(repoRoot);
  assert.ok(allHtmlFiles.length > 100, "Repository should contain HTML files");

  const outdatedLinks = [];
  const validToolLinks = [];

  for (const filePath of allHtmlFiles) {
    const rel = path.relative(repoRoot, filePath);
    // Skip redirect stubs themselves from in-site link check
    if (rel === "tools/wake-window-calculator.html" || rel === "tools/sleep-milestone-calculator.html") {
      continue;
    }

    const content = fs.readFileSync(filePath, "utf-8");
    const hrefMatches = content.matchAll(/href="([^"]+)"/g);

    for (const match of hrefMatches) {
      const href = match[1];
      if (href.includes("wake-window-calculator.html") || href.includes("sleep-milestone-calculator.html")) {
        outdatedLinks.push({ file: rel, href });
      }
      if (href.startsWith("/tools/wake-window-calculator/") || href.startsWith("/tools/sleep-milestone-calculator/")) {
        validToolLinks.push({ file: rel, href });
      }
    }
  }

  assert.strictEqual(
    outdatedLinks.length,
    0,
    `Found ${outdatedLinks.length} outdated .html tool links: ${JSON.stringify(outdatedLinks)}`
  );
  assert.ok(
    validToolLinks.length >= 20,
    `Expected at least 20 in-site tool links pointing to canonical directories, found ${validToolLinks.length}`
  );
});
