import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

const wwPath = path.join(repoRoot, "tools/wake-window-calculator/index.html");
const msPath = path.join(repoRoot, "tools/sleep-milestone-calculator.html");

const wwHtml = fs.readFileSync(wwPath, "utf8");
const msHtml = fs.readFileSync(msPath, "utf8");

/* Helper to extract the main script block from HTML */
function extractMainScript(html, matchPattern) {
  const scriptRegex = /<script>([\s\S]*?)<\/script>/gi;
  let match;
  while ((match = scriptRegex.exec(html)) !== null) {
    if (matchPattern.test(match[1])) {
      return match[1];
    }
  }
  throw new Error("Could not find script matching pattern: " + matchPattern);
}

const wwScript = extractMainScript(wwHtml, /var AGE_DATA/);
const msScript = extractMainScript(msHtml, /var BANDS/);

/* Helper to extract AGE_DATA and NOTES from Wake Window script */
function getWakeWindowData() {
  const sandbox = {};
  const code = `
    ${wwScript.slice(0, wwScript.indexOf("function fmt("))}
    exports.AGE_DATA = AGE_DATA;
    exports.NOTES = NOTES;
  `;
  const script = new vm.Script(`(function(exports) { ${code} })(sandbox)`);
  const context = vm.createContext({ sandbox });
  script.runInContext(context);
  return sandbox;
}

/* Helper to extract BANDS from Milestone script */
function getMilestoneBands() {
  const sandbox = {};
  const code = `
    ${msScript.slice(0, msScript.indexOf("var ICONS ="))}
    exports.BANDS = BANDS;
  `;
  const script = new vm.Script(`(function(exports) { ${code} })(sandbox)`);
  const context = vm.createContext({ sandbox });
  script.runInContext(context);
  return sandbox.BANDS;
}

/* Helper to create a mock DOM element */
function createMockElement(id = "", tagName = "div") {
  let _val = "";
  const el = {
    id,
    tagName: tagName.toUpperCase(),
    get value() { return _val; },
    set value(v) { _val = v !== undefined && v !== null ? String(v) : ""; },
    textContent: "",
    innerHTML: "",
    href: "",
    style: { display: "" },
    attributes: {},
    listeners: {},
    setAttribute(k, v) { this.attributes[k] = String(v); },
    getAttribute(k) { return this.attributes[k] !== undefined ? this.attributes[k] : null; },
    addEventListener(evt, fn) {
      if (!this.listeners[evt]) this.listeners[evt] = [];
      this.listeners[evt].push(fn);
    },
    dispatchEvent(evt) {
      const fns = this.listeners[evt] || [];
      for (const fn of fns) fn();
    },
    querySelector(sel) {
      return createMockElement("", "div");
    },
    querySelectorAll(sel) {
      return [];
    }
  };
  return el;
}

/* Helper to instantiate Wake Window runtime environment in VM */
function runWakeWindowRuntime(options = {}) {
  const elements = {};
  const getEl = (id) => {
    if (!elements[id]) elements[id] = createMockElement(id);
    return elements[id];
  };

  const slider = getEl("age-slider");
  slider.value = options.sliderValue !== undefined ? String(options.sliderValue) : "6";

  const wakeTime = getEl("wake-time");
  wakeTime.value = options.wakeTime || "07:00";

  getEl("age-readout");
  getEl("age-years");
  getEl("band-label");
  getEl("schedule-rows");
  getEl("ww-chip");
  getEl("naps-chip");
  getEl("total-chip");
  getEl("band-note");
  getEl("link-milestone-calc");

  const storage = { ...(options.sessionStorage || {}) };
  const historyCalls = [];

  const windowMock = {
    location: {
      href: options.url || "https://snugs.ai/tools/wake-window-calculator/",
      search: options.search || "",
      origin: "https://snugs.ai",
      pathname: "/tools/wake-window-calculator/"
    },
    history: {
      replaceState(state, title, url) {
        historyCalls.push({ state, title, url });
        windowMock.location.href = url;
      }
    },
    sessionStorage: {
      getItem(k) { return storage[k] !== undefined ? storage[k] : null; },
      setItem(k, v) { storage[k] = String(v); }
    },
    addEventListener() {}
  };

  const docMock = {
    getElementById(id) { return getEl(id); },
    querySelector(sel) { return createMockElement("", "div"); },
    querySelectorAll(sel) { return []; }
  };

  const sandbox = {
    window: windowMock,
    document: docMock,
    sessionStorage: windowMock.sessionStorage,
    URLSearchParams: globalThis.URLSearchParams,
    URL: globalThis.URL,
    parseInt: globalThis.parseInt,
    Math: globalThis.Math
  };

  vm.createContext(sandbox);
  vm.runInContext(wwScript, sandbox);

  return { elements, storage, historyCalls, sandbox };
}

/* Helper to instantiate Milestone runtime environment in VM */
function runMilestoneRuntime(options = {}) {
  const elements = {};
  const getEl = (id) => {
    if (!elements[id]) elements[id] = createMockElement(id);
    return elements[id];
  };

  const slider = getEl("age-slider");
  slider.value = options.sliderValue !== undefined ? String(options.sliderValue) : "24";

  getEl("age-readout");
  getEl("age-years");
  getEl("below-six-card");
  getEl("below-six-age-text");
  getEl("below-six-btn-age");
  getEl("below-six-link");
  getEl("schedule-section");
  getEl("milestone-section");
  getEl("band-label");
  getEl("schedule-rows");
  getEl("total-sleep");
  getEl("band-note");
  getEl("band-tip");
  getEl("milestone-list");
  getEl("milestone-progress-bar");
  getEl("milestone-progress-text");
  getEl("cta-trial");
  getEl("copy-link");
  getEl("keep-reading-ww");

  const storage = { ...(options.sessionStorage || {}) };
  const historyCalls = [];

  const windowMock = {
    location: {
      href: options.url || "https://snugs.ai/tools/sleep-milestone-calculator.html",
      search: options.search || "",
      origin: "https://snugs.ai",
      pathname: "/tools/sleep-milestone-calculator.html"
    },
    history: {
      replaceState(state, title, url) {
        historyCalls.push({ state, title, url });
        windowMock.location.href = url;
      }
    },
    sessionStorage: {
      getItem(k) { return storage[k] !== undefined ? storage[k] : null; },
      setItem(k, v) { storage[k] = String(v); }
    },
    localStorage: {
      getItem() { return null; },
      setItem() {}
    },
    addEventListener() {}
  };

  const docMock = {
    getElementById(id) { return getEl(id); },
    querySelector(sel) { return createMockElement("", "div"); },
    querySelectorAll(sel) { return []; }
  };

  const sandbox = {
    window: windowMock,
    document: docMock,
    sessionStorage: windowMock.sessionStorage,
    localStorage: windowMock.localStorage,
    URLSearchParams: globalThis.URLSearchParams,
    URL: globalThis.URL,
    parseInt: globalThis.parseInt,
    Math: globalThis.Math,
    JSON: globalThis.JSON,
    showToast: () => {}
  };

  vm.createContext(sandbox);
  vm.runInContext(msScript, sandbox);

  return { elements, storage, historyCalls, sandbox };
}

/* =========================================================================
   TESTS
   ========================================================================= */

test("Wake Window Calculator data at 6 months agrees with updated guidelines (#35)", () => {
  const { AGE_DATA } = getWakeWindowData();
  const d6 = AGE_DATA[6];

  assert.equal(d6.ww, "2–3 h", "6 months wake window range is 2–3 h");
  assert.equal(d6.nt, "2–3", "6 months nap count is 2–3 naps");
  assert.equal(d6.tt, "12–15 h", "6 months total sleep is 12–15 h");
  assert.equal(d6.bed, 720, "6 months bedtime offset is 720 min (7:00 PM baseline from 7:00 AM wake)");
});

test("Wake Window Calculator static HTML table row for 6 months reflects updated data (#35)", () => {
  const rowMatch = wwHtml.match(/<th[^>]*>6 months<\/th>\s*<td[^>]*>([^<]+)<\/td>\s*<td[^>]*>([^<]+)<\/td>\s*<td[^>]*>([^<]+)<\/td>\s*<td[^>]*>([^<]+)<\/td>/i);
  assert.ok(rowMatch, "Found 6 months table row in wake window calculator");

  const [, ww, naps, napLen, total] = rowMatch;
  assert.equal(ww.trim(), "2–3 h", "Table shows 2–3 h wake windows at 6 months");
  assert.equal(naps.trim(), "2–3", "Table shows 2–3 naps at 6 months");
  assert.equal(total.trim(), "12–15 h", "Table shows 12–15 h total sleep at 6 months");
});

test("Wake Window Calculator NOTES[6] explains 3-to-2 nap transition and bedtime differences (#35)", () => {
  const { NOTES } = getWakeWindowData();
  const note6 = NOTES[6];

  assert.ok(note6, "NOTES[6] exists");
  assert.match(note6, /3-to-2 nap transition/i, "Mentions 3-to-2 nap transition");
  assert.match(note6, /12–15 hours/i, "States 12–15 hours total sleep");
  assert.match(note6, /7:00–7:30 PM/i, "Mentions 7:00–7:30 PM bedtime on 2 naps");
  assert.match(note6, /7:30–8:00 PM/i, "Mentions 7:30–8:00 PM bedtime on 3 naps");
  assert.match(note6, /2\.5–3 h/i, "Mentions 2.5–3 h wake windows on 2 naps");
  assert.match(note6, /2–2\.5 h/i, "Mentions 2–2.5 h wake windows on 3 naps");
});

test("Sleep Milestone Calculator 6–9 month band data aligns with 6-month guidelines (#35)", () => {
  const bands = getMilestoneBands();
  const band6 = bands.find((b) => b.min === 6 && b.max === 9);

  assert.ok(band6, "6–9 months band exists");
  assert.match(band6.total, /12–15 hours total/i, "Band 6-9 total sleep is 12–15 hours");
  assert.match(band6.total, /2–3 naps/i, "Band 6-9 total sleep specifies 2–3 naps");
  assert.match(band6.note, /2–3 naps\/day/i, "Band 6-9 note states 2–3 naps/day");
  assert.match(band6.note, /3-to-2 nap transition/i, "Band 6-9 note states 3-to-2 nap transition window");
  assert.match(band6.tip, /7:30–8:00 PM/i, "Band 6-9 tip states 7:30–8:00 PM bedtime on 3 naps");
  assert.match(band6.tip, /7:00–7:30 PM/i, "Band 6-9 tip states 7:00–7:30 PM bedtime on 2 naps");
  assert.match(band6.tip, /2–2\.5 h/i, "Band 6-9 tip states 2–2.5 h wake windows on 3 naps");
  assert.match(band6.tip, /2\.5–3 h/i, "Band 6-9 tip states 2.5–3 h wake windows on 2 naps");
});

test("At 6 months, both tools agree on nap count, wake windows, bedtime range, and total sleep (#35)", () => {
  const { AGE_DATA } = getWakeWindowData();
  const bands = getMilestoneBands();
  const ww6 = AGE_DATA[6];
  const ms6 = bands.find((b) => b.min === 6);

  // Nap count agreement: 2-3 naps
  assert.equal(ww6.nt, "2–3");
  assert.match(ms6.note, /2–3 naps/);

  // Total sleep agreement: 12-15 hours
  assert.equal(ww6.tt, "12–15 h");
  assert.match(ms6.total, /12–15 hours/);

  // Wake window agreement: 2-3 hours
  assert.equal(ww6.ww, "2–3 h");
  assert.match(ms6.tip, /2–2\.5 h/);
  assert.match(ms6.tip, /2\.5–3 h/);

  // Bedtime explanation agreement: 7:00-7:30 PM on 2 naps, 7:30-8:00 PM on 3 naps
  const { NOTES } = getWakeWindowData();
  assert.match(NOTES[6], /7:00–7:30 PM/);
  assert.match(NOTES[6], /7:30–8:00 PM/);
  assert.match(ms6.tip, /7:00–7:30 PM/);
  assert.match(ms6.tip, /7:30–8:00 PM/);
});

test("Wake Window Calculator covers 4-month-olds directly (#35)", () => {
  const { AGE_DATA } = getWakeWindowData();
  const d4 = AGE_DATA[4];

  assert.ok(d4, "AGE_DATA[4] exists");
  assert.equal(d4.ww, "1.5–2 h", "4 months wake window is 1.5–2 h");
  assert.equal(d4.nt, "3", "4 months nap count is 3");
  assert.equal(d4.tt, "12–15 h", "4 months total sleep is 12–15 h");
  assert.equal(d4.bed, 780, "4 months bedtime is 780 min (8:00 PM baseline from 7:00 AM wake)");
});

test("Sleep Milestone Calculator slider starts at 0 months without silent clamp (#35)", () => {
  const sliderMatch = msHtml.match(/<input[^>]*id="age-slider"[^>]*>/i);
  assert.ok(sliderMatch, "Found age slider in milestone calculator");
  const inputTag = sliderMatch[0];

  assert.match(inputTag, /min="0"/, "Slider min attribute is 0, not 6");
  assert.match(inputTag, /max="60"/, "Slider max attribute is 60");
  assert.match(msHtml, /<span>0 months \(newborn\)<\/span>/, "Scale label starts at 0 months (newborn)");
});

test("Sleep Milestone Calculator at 4 months shows dedicated notice and direct link to Wake Window (#35)", () => {
  const rt = runMilestoneRuntime({ sliderValue: 4 });
  const { elements } = rt;

  // Age readout reflects entered age (no silent clamp to 6)
  assert.equal(elements["age-readout"].textContent, "4 months", "Readout shows 4 months");
  assert.equal(elements["age-slider"].value, "4", "Slider value is 4");

  // Under-six card is visible and styled with CTA link
  assert.equal(elements["below-six-card"].style.display, "", "Below six card is visible");
  assert.equal(elements["below-six-age-text"].textContent, "4 months", "Notice specifies 4 months");
  assert.equal(elements["below-six-btn-age"].textContent, "4 months", "CTA button specifies 4 months");
  assert.equal(elements["below-six-link"].href, "/tools/wake-window-calculator/?age=4", "Link points to wake window calculator with age=4");

  // Schedule and milestone checklist sections are hidden
  assert.equal(elements["schedule-section"].style.display, "none", "Schedule section is hidden");
  assert.equal(elements["milestone-section"].style.display, "none", "Milestone section is hidden");
  assert.equal(elements["schedule-rows"].innerHTML, "", "Schedule rows are cleared");
  assert.equal(elements["milestone-list"].innerHTML, "", "Milestone list is cleared");
});

test("Sleep Milestone Calculator cleanly recalculates without leftover copy when sliding between ages (#35)", () => {
  const rt = runMilestoneRuntime({ sliderValue: 4 });
  const { elements, sandbox } = rt;

  // At 4 months: schedule and milestone sections are hidden and empty
  assert.equal(elements["below-six-card"].style.display, "");
  assert.equal(elements["schedule-section"].style.display, "none");
  assert.equal(elements["milestone-section"].style.display, "none");
  assert.equal(elements["schedule-rows"].innerHTML, "");
  assert.equal(elements["milestone-list"].innerHTML, "");

  // Slide to 6 months
  elements["age-slider"].value = "6";
  sandbox.render();

  assert.equal(elements["below-six-card"].style.display, "none", "Below six card hidden at 6m");
  assert.equal(elements["schedule-section"].style.display, "", "Schedule section shown at 6m");
  assert.equal(elements["milestone-section"].style.display, "", "Milestone section shown at 6m");
  assert.equal(elements["band-label"].textContent, "6–9 months");
  assert.match(elements["total-sleep"].textContent, /12–15 hours total/);
  assert.match(elements["band-note"].textContent, /2–3 naps\/day/);
  assert.match(elements["schedule-rows"].innerHTML, /Nap 3 \(catnap\)/, "6-9m schedule includes catnap");
  assert.match(elements["milestone-list"].innerHTML, /Rolls over in both directions/, "6-9m milestones rendered");

  // Slide to 18 months
  elements["age-slider"].value = "18";
  sandbox.render();

  assert.equal(elements["band-label"].textContent, "18–24 months");
  assert.match(elements["total-sleep"].textContent, /11–14 hours total/);
  assert.doesNotMatch(elements["schedule-rows"].innerHTML, /Nap 3 \(catnap\)/, "18m has no catnap leftover");
  assert.doesNotMatch(elements["milestone-list"].innerHTML, /Rolls over in both directions/, "No 6m milestone leftover");
  assert.match(elements["milestone-list"].innerHTML, /Kicks a ball forward/, "18m milestones rendered");

  // Slide back to 4 months
  elements["age-slider"].value = "4";
  sandbox.render();

  assert.equal(elements["below-six-card"].style.display, "", "Below six card shown again at 4m");
  assert.equal(elements["schedule-section"].style.display, "none", "Schedule section hidden again at 4m");
  assert.equal(elements["milestone-section"].style.display, "none", "Milestone section hidden again at 4m");
  assert.equal(elements["schedule-rows"].innerHTML, "", "Schedule rows completely empty at 4m");
  assert.equal(elements["milestone-list"].innerHTML, "", "Milestone list completely empty at 4m");
});

test("Wake Window Calculator state preservation: loads age from URL query param and syncs history (#35)", () => {
  const rt4 = runWakeWindowRuntime({ search: "?age=4" });
  assert.equal(rt4.elements["age-slider"].value, "4", "Wake window calculator sets slider to 4 from ?age=4");
  assert.equal(rt4.elements["age-readout"].textContent, "4 months");
  assert.equal(rt4.elements["ww-chip"].textContent, "Wake windows: 1.5–2 h");
  assert.equal(rt4.elements["naps-chip"].textContent, "3 naps/day");

  // Cross-link to milestone calculator preserves age
  assert.equal(rt4.elements["link-milestone-calc"].href, "/tools/sleep-milestone-calculator.html?age=4");

  // Changing slider records state in sessionStorage and calls replaceState
  rt4.elements["age-slider"].value = "6";
  rt4.elements["age-slider"].dispatchEvent("input");

  assert.equal(rt4.storage["snugs_tool_age"], "6", "sessionStorage saved age 6");
  assert.ok(rt4.historyCalls.length > 0, "history.replaceState was called");
  const lastHistory = rt4.historyCalls[rt4.historyCalls.length - 1];
  assert.equal(lastHistory.state.age, 6, "History state contains age 6");
  assert.match(lastHistory.url, /age=6/, "History URL updated with ?age=6");
  assert.equal(rt4.elements["link-milestone-calc"].href, "/tools/sleep-milestone-calculator.html?age=6");
});

test("Sleep Milestone Calculator state preservation: loads age from URL query param and syncs history (#35)", () => {
  const rt6 = runMilestoneRuntime({ search: "?age=6" });
  assert.equal(rt6.elements["age-slider"].value, "6", "Milestone calculator sets slider to 6 from ?age=6");
  assert.equal(rt6.elements["age-readout"].textContent, "6 months");
  assert.equal(rt6.elements["band-label"].textContent, "6–9 months");
  assert.equal(rt6.elements["keep-reading-ww"].href, "/tools/wake-window-calculator/?age=6");

  // Changing slider records state in sessionStorage and calls replaceState
  rt6.elements["age-slider"].value = "4";
  rt6.elements["age-slider"].dispatchEvent("input");

  assert.equal(rt6.storage["snugs_tool_age"], "4", "sessionStorage saved age 4");
  assert.ok(rt6.historyCalls.length > 0, "history.replaceState was called");
  const lastHistory = rt6.historyCalls[rt6.historyCalls.length - 1];
  assert.equal(lastHistory.state.age, 4, "History state contains age 4");
  assert.match(lastHistory.url, /age=4/, "History URL updated with ?age=4");
  assert.equal(rt6.elements["keep-reading-ww"].href, "/tools/wake-window-calculator/?age=4");
});

test("Sleep Milestone Calculator handles newborn (0m) and 5m as under-six without silent clamp (#35)", () => {
  const rt0 = runMilestoneRuntime({ search: "?age=0" });
  assert.equal(rt0.elements["age-slider"].value, "0");
  assert.equal(rt0.elements["age-readout"].textContent, "0 months (Newborn)");
  assert.equal(rt0.elements["below-six-card"].style.display, "");
  assert.equal(rt0.elements["below-six-link"].href, "/tools/wake-window-calculator/?age=0");
  assert.equal(rt0.elements["schedule-section"].style.display, "none");

  const rt5 = runMilestoneRuntime({ search: "?age=5" });
  assert.equal(rt5.elements["age-slider"].value, "5");
  assert.equal(rt5.elements["age-readout"].textContent, "5 months");
  assert.equal(rt5.elements["below-six-card"].style.display, "");
  assert.equal(rt5.elements["below-six-link"].href, "/tools/wake-window-calculator/?age=5");
  assert.equal(rt5.elements["schedule-section"].style.display, "none");
});

test("Wake Window Calculator handles custom wake time and newborn (0m) (#35)", () => {
  const rtWake = runWakeWindowRuntime({ search: "?age=0&wake=08:30" });
  assert.equal(rtWake.elements["age-slider"].value, "0");
  assert.equal(rtWake.elements["age-readout"].textContent, "Newborn");
  assert.equal(rtWake.elements["wake-time"].value, "08:30");
  assert.match(rtWake.elements["schedule-rows"].innerHTML, /8:30 AM/, "Schedule starts at 8:30 AM");
});

test("Sleep Milestone Calculator copy share link includes current entered age (#35)", () => {
  const rt = runMilestoneRuntime({ sliderValue: 4 });
  let copiedUrl = null;
  rt.sandbox.navigator = {
    clipboard: {
      writeText: async (text) => { copiedUrl = text; }
    }
  };

  rt.elements["copy-link"].dispatchEvent("click");
  assert.equal(copiedUrl, "https://snugs.ai/tools/sleep-milestone-calculator.html?age=4", "Share link preserves entered age");
});
