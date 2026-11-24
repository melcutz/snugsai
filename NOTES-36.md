# Notes for Issue #36: Sleep Tools Internal Consistency

## Overview
This change resolves internal contradictions within the Wake Window Calculator and the Nap Transition Checker.

## Bug 1: Wake Window Calculator 4-Month Schedule Contradiction

### Before
- For a 4-month-old child, the chart and "Wake windows" chip stated a range of 1.5-2 h with 3 naps (AGE_DATA[4] had ww "1.5-2 h", nt "3").
- The computed day schedule from a 7:00 AM wake was:
  - Wake: 7:00 AM
  - Nap 1: 9:00 AM to 10:30 AM (2.0 h awake)
  - Nap 2: 12:30 PM to 2:00 PM (2.0 h awake)
  - Nap 3: 4:30 PM to 6:00 PM (2.5 h awake)
  - Bedtime: 8:00 PM (2.0 h awake)
- The third wake window was 2.5 hours, which exceeded the printed 1.5-2 h range on the exact same page.

### After (Fixed)
- Updated AGE_DATA[4].ww and the static table row for 4 months to "1.5-2.5 h", accurately covering all computed wake windows (2.0 h, 2.0 h, 2.5 h, 2.0 h).
- Updated the table header to "Typical wake window" and clarified the guidance note: "Every child is different: these are typical ranges, not exact targets. Watch sleepy cues and shift times by 15-30 minutes to fit your family."
- Updated the chip display and existing tests to reflect the 1.5-2.5 h typical range.

## Bug 2: Nap Transition Checker Contradictory "Too Early" Advice

### Before
- When a user submitted inputs indicating an age under 5 months (3 or more naps, Under 5 months, falling asleep at nap time most days, bedtime drifting later, pattern lasting 1-2 weeks), the checker returned conflicting guidance on a single card:
  - Headline verdict: "Probably too early -- keep your current schedule."
  - Yellow note: Child is on the young side.
  - Subheading on the same card: "LIKELY TRANSITION: 3 NAPS -> 2 NAPS".
  - Primary step-by-step plan: 4-step plan to drop the catnap.
- A parent of a child under 5 months received both a recommendation not to transition and instructions on how to transition immediately.
- Re-calculating or changing inputs did not provide seamless in-place replacement.

### After (Fixed)
- When the transition is evaluated as too early:
  - The headline clearly communicates: "Probably too early -- keep your current schedule."
  - The "LIKELY TRANSITION" badge is hidden and cleared.
  - The plan heading is changed to "What to do now".
  - The primary action plan renders age-appropriate guidance on protecting the current nap count and managing temporary regressions, rather than dropping a nap.
  - Any future transition details are placed inside a separate, clearly marked preview box: "Later-age preview (typical at 5-8 months)" with collapsible future transition steps.
- When ready for transition (e.g. 5-8 months):
  - Shows "Likely transition: 3 naps -> 2 naps".
  - Heading displays "Your plan".
  - Primary steps provide the transition plan.
  - Preview box is hidden.
- Recalculating or changing an input automatically updates the single result card in place without stacking cards, and user form selections remain preserved.

## Verification
- Added test suite `tests/test_sleep_tools_consistency_36.mjs` verifying:
  - At 4 months, every computed wake window on the day schedule falls inside the printed 1.5-2.5 h range.
  - Static HTML table and chips align with typical ranges.
  - Under 5 months quiz submissions show the too-early path with no primary transition plan and clear later-age preview.
  - Dynamic updates replace results in-place while preserving form inputs.
- All existing tests in `tests/test_sleep_tools_consistency.mjs` pass.
- SEO script `scripts/verify_seo.py` passes all checks.
