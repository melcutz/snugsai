import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

test("favicon assets exist with correct dimensions", () => {
  const icoPath = path.join(repoRoot, "favicon.ico");
  const svgPath = path.join(repoRoot, "favicon.svg");
  const applePath = path.join(repoRoot, "apple-touch-icon.png");

  assert.ok(fs.existsSync(icoPath), "favicon.ico must exist");
  assert.ok(fs.existsSync(svgPath), "favicon.svg must exist");
  assert.ok(fs.existsSync(applePath), "apple-touch-icon.png must exist");

  const icoBuf = fs.readFileSync(icoPath);
  assert.equal(icoBuf.readUInt16LE(0), 0, "ICO reserved bytes must be 0");
  assert.equal(icoBuf.readUInt16LE(2), 1, "ICO type must be 1 (icon)");
  const imgCount = icoBuf.readUInt16LE(4);
  assert.ok(imgCount >= 1, "ICO must contain at least 1 image");
  const widthByte = icoBuf.readUInt8(6);
  const heightByte = icoBuf.readUInt8(7);
  assert.equal(widthByte, 32, "favicon.ico width must be 32px");
  assert.equal(heightByte, 32, "favicon.ico height must be 32px");

  const pngBuf = fs.readFileSync(applePath);
  assert.equal(pngBuf.toString("ascii", 1, 4), "PNG", "apple-touch-icon must be a PNG");
  const pngWidth = pngBuf.readUInt32BE(16);
  const pngHeight = pngBuf.readUInt32BE(20);
  assert.equal(pngWidth, 180, "apple-touch-icon width must be 180px");
  assert.equal(pngHeight, 180, "apple-touch-icon height must be 180px");
});

test("index.html and pages with rel=icon point to favicon.svg and apple-touch-icon", () => {
  const indexPath = path.join(repoRoot, "index.html");
  const indexHtml = fs.readFileSync(indexPath, "utf-8");

  assert.match(indexHtml, /rel=["']icon["'][^>]*favicon\.svg|favicon\.svg[^>]*rel=["']icon["']/);
  assert.doesNotMatch(indexHtml, /rel=["']icon["'][^>]*\/og\/snugs-og\.jpg/);
  assert.match(indexHtml, /rel=["']apple-touch-icon["'][^>]*apple-touch-icon\.png/);

  function walk(dir) {
    let files = [];
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      if (ent.name === ".git" || ent.name === "node_modules") continue;
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        files = files.concat(walk(full));
      } else if (ent.name.endsWith(".html")) {
        files.push(full);
      }
    }
    return files;
  }

  const allHtml = walk(repoRoot);
  let checked = 0;
  for (const f of allHtml) {
    const content = fs.readFileSync(f, "utf-8");
    if (content.includes('rel="icon"') || content.includes("rel='icon'")) {
      checked++;
      assert.ok(
        content.includes("/favicon.svg"),
        f + " has rel=icon but does not point to /favicon.svg"
      );
      assert.ok(
        !content.match(/rel=["']icon["'][^>]*\/og\/snugs-og\.jpg/),
        f + " still uses snugs-og.jpg as rel=icon"
      );
      assert.ok(
        content.includes("/apple-touch-icon.png"),
        f + " is missing apple-touch-icon"
      );
    }
  }
  assert.ok(checked >= 400, "Should have checked all pages with favicons");
});

test("no in-repo HTML files link to wake-window-calculator.html", () => {
  function walk(dir) {
    let files = [];
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      if (ent.name === ".git" || ent.name === "node_modules") continue;
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        files = files.concat(walk(full));
      } else if (ent.name.endsWith(".html")) {
        files.push(full);
      }
    }
    return files;
  }

  const allHtml = walk(repoRoot);
  for (const f of allHtml) {
    const content = fs.readFileSync(f, "utf-8");
    assert.ok(
      !content.includes("wake-window-calculator.html"),
      "Found broken link in " + f
    );
  }
});

test("crawl of sitemap URLs finds no internal 404 links", () => {
  const sitemapPath = path.join(repoRoot, "sitemap.xml");
  const sitemapXml = fs.readFileSync(sitemapPath, "utf-8");

  const locMatches = [...sitemapXml.matchAll(/<loc>\s*(https:\/\/snugs\.ai\/[^<]*)\s*<\/loc>/g)];
  assert.ok(locMatches.length > 0, "sitemap.xml must contain URLs");

  const hrefRegex = /<(?:a|link)\b[^>]*?\bhref=["']([^"']+)["']/gi;
  const brokenLinks = [];

  for (const m of locMatches) {
    const url = m[1];
    let rel = url.replace("https://snugs.ai/", "");
    if (!rel || rel.endsWith("/")) {
      rel = path.join(rel, "index.html");
    }
    const sourceFile = path.join(repoRoot, rel);
    assert.ok(fs.existsSync(sourceFile), "Sitemap source file must exist: " + sourceFile);

    const html = fs.readFileSync(sourceFile, "utf-8");
    let match;
    while ((match = hrefRegex.exec(html)) !== null) {
      const href = match[1];

      if (
        href.startsWith("#") ||
        href.startsWith("mailto:") ||
        href.startsWith("tel:") ||
        href.startsWith("javascript:")
      ) {
        continue;
      }

      if (href.startsWith("http://") || href.startsWith("https://")) {
        if (!href.startsWith("https://snugs.ai/") && !href.startsWith("http://snugs.ai/")) {
          continue;
        }
      }

      let cleanPath = href.replace(/^https?:\/\/snugs\.ai/, "");
      cleanPath = cleanPath.split("#")[0].split("?")[0];
      if (!cleanPath || cleanPath === "/") continue;

      let target;
      if (cleanPath.startsWith("/")) {
        target = path.join(repoRoot, cleanPath.slice(1));
      } else {
        target = path.join(path.dirname(sourceFile), cleanPath);
      }

      let exists = false;
      if (fs.existsSync(target)) {
        if (fs.statSync(target).isDirectory()) {
          exists = fs.existsSync(path.join(target, "index.html"));
        } else {
          exists = true;
        }
      } else if (fs.existsSync(target + ".html")) {
        exists = true;
      }

      if (!exists) {
        brokenLinks.push({ source: rel, href });
      }
    }
  }

  assert.equal(
    brokenLinks.length,
    0,
    "Found broken internal links in sitemap pages: " + JSON.stringify(brokenLinks, null, 2)
  );
});

test("CTA links preserve UTM and plan parameters", () => {
  const indexPath = path.join(repoRoot, "index.html");
  const indexHtml = fs.readFileSync(indexPath, "utf-8");

  assert.ok(indexHtml.includes("plan=monthly"), "index.html must preserve plan=monthly param");
  assert.ok(indexHtml.includes("plan=yearly"), "index.html must preserve plan=yearly param");
  assert.ok(
    indexHtml.includes("utm_source=marketing_site") && indexHtml.includes("utm_medium=cta"),
    "index.html CTAs must preserve utm params"
  );
});
