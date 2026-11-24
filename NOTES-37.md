# Site Polish Notes (#37)

## Overview
This document summarizes before and after behavior for the site polish updates addressing mobile hero CTA placement, share image download control visibility, and tool URL standardization.

## 1. Mobile Hero CTA Placement

### Before
- On mobile viewports (e.g. 390px iPhone screen), visitors saw the top nav, a large bear illustration (240px wide), the badge, and the primary headline ("Your Baby Won't Sleep. It's 3AM.").
- The trial CTA button ("Start your 14-day free trial") was placed underneath a long description paragraph and feature list, requiring the user to scroll down to view and interact with the primary conversion action.

### After
- Scaled the bear illustration on mobile screens to `w-40 h-40` (`160px`) and `sm:w-56 sm:h-56` (`224px`), while preserving `lg:w-[400px] lg:h-[400px]` on desktop.
- Reduced excessive top header margin on mobile from `mb-16 lg:mb-24` to `mb-8 md:mb-16 lg:mb-24`.
- Added a dedicated mobile CTA button directly below the headline and subhead (`block lg:hidden`) positioned above the fold.
- Desktop CTA container hidden on mobile (`hidden lg:block`) to avoid duplicate buttons during scrolling.
- Preserved all required query parameters and tracking attributes on mobile and desktop links: `data-cta="home-hero"`, `utm_source=marketing_site`, `utm_medium=cta`, and `utm_campaign=home-hero`.
- Result: Fixed so phone visitors at 390px see the trial CTA without needing to scroll.

## 2. Hide Share Image Download Control

### Before
- Under the "Share the love" section on the homepage (`index.html`), an author debug button labeled "Download share image (1200x630)" was publicly visible.
- Parents visiting the site do not need author/debug asset download tools.

### After
- Removed the public "Download share image (1200x630)" link element from `index.html`.
- Preserved all public sharing buttons and platform handlers (Facebook, Reddit, Instagram, TikTok, WhatsApp, LinkedIn, X).
- Maintained all FAQ accordion components (`<details>` / `<summary>`) and section styling intact.
- Result: Fixed public homepage clutter while retaining full social sharing functionality.

## 3. Tool URL Naming and Redirects

### Before
- Wake Window Calculator lived at directory path `/tools/wake-window-calculator/` (returned 200, but `/tools/wake-window-calculator.html` returned 404).
- Sleep Milestone Calculator lived at `/tools/sleep-milestone-calculator.html` (returned 200, but `/tools/sleep-milestone-calculator/` returned 404).
- Inconsistent URL conventions across tools and in-site navigation links.

### After
- Standardized canonical tool URLs on directory paths with trailing slashes:
  - Canonical Wake Window Calculator: `/tools/wake-window-calculator/`
  - Canonical Sleep Milestone Calculator: `/tools/sleep-milestone-calculator/`
- Created `tools/sleep-milestone-calculator/index.html` as the canonical document, with updated canonical tags, Open Graph URLs, and breadcrumb schema.
- Added static redirect stubs:
  - `tools/wake-window-calculator.html` redirects to `/tools/wake-window-calculator/`.
  - `tools/sleep-milestone-calculator.html` redirects to `/tools/sleep-milestone-calculator/`.
  - Both stubs use `<meta http-equiv="refresh">`, canonical link tags, `noindex` robots meta, unique page titles, and fallback links.
- Updated in-site tool links across `index.html`, `tools/index.html`, tool pages, and resource articles to use canonical directory paths.
- Updated `sitemap.xml`, inventory documentation, and verification scripts to reflect canonical directory paths.
- Result: Both tool URLs resolve without 404 whether requested with `.html` or with a trailing slash directory path.

## 4. Automated Verification

- Added `tests/test_site_polish_37.mjs` verifying:
  1. Mobile hero CTA markup and above-the-fold placement before the intro paragraph with proper UTM parameters.
  2. Removal of download share image control without regression to social share buttons or FAQ accordions.
  3. Resolution of canonical tool URLs and redirect stubs for both tools with and without `.html`.
  4. In-site link health ensuring zero outdated `.html` tool links across site HTML pages.
