import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");

const wwPath = path.join(repoRoot, "tools/wake-window-calculator/index.html");
const napPath = path.join(repoRoot, "tools/nap-transition-checker/index.html");

const wwHtml = fs.readFileSync(wwPath, "utf8");
const napHtml = fs.readFileSync(napPath, "utf8");

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

/* ========================================================================== */
/* Wake Window Calculator tests (#36)                                        */
/* ========================================================================== */

const wwScript = extractMainScript(wwHtml, /var AGE_DATA/);

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

test("Wake Window Calculator at 4 months: every computed wake window falls inside printed range (#36)", () => {
  const { AGE_DATA } = getWakeWindowData();
  const d4 = AGE_DATA[4];

  assert.ok(d4, "AGE_DATA[4] exists");
  assert.equal(d4.ww, "1.5-2.5 h", "Printed range in AGE_DATA[4] is 1.5-2.5 h");
  assert.equal(d4.nt, "3", "4-month-olds have 3 naps");

  // Parse min and max from printed range "1.5-2.5 h"
  const rangeMatch = d4.ww.match(/^([0-9.]+)-([0-9.]+)\s*h$/);
  assert.ok(rangeMatch, "Range pattern parsed");
  const minRangeHours = parseFloat(rangeMatch[1]);
  const maxRangeHours = parseFloat(rangeMatch[2]);

  // Compute the wake windows for a standard day (wake = 0)
  const wake = 0; // e.g. 7:00 AM baseline
  const napStarts = d4.ns;
  const napDuration = d4.d;
  const bedtime = d4.bed;

  const wakeWindowsMinutes = [];
  let prevEnd = wake;
  for (let i = 0; i < napStarts.length; i++) {
    const napStart = napStarts[i];
    wakeWindowsMinutes.push(napStart - prevEnd);
    prevEnd = napStart + napDuration;
  }
  // Wake window before bed
  wakeWindowsMinutes.push(bedtime - prevEnd);

  // Computed wake windows from 7:00 AM wake:
  // Nap 1: 120 min = 2.0 h
  // Nap 2: 120 min = 2.0 h
  // Nap 3: 150 min = 2.5 h
  // Bedtime: 120 min = 2.0 h
  assert.deepEqual(wakeWindowsMinutes, [120, 120, 150, 120]);

  for (const winMin of wakeWindowsMinutes) {
    const winHours = winMin / 60;
    assert.ok(
      winHours >= minRangeHours && winHours <= maxRangeHours,
      `Wake window of ${winHours} h must fall inside printed range [${minRangeHours}, ${maxRangeHours}] h`
    );
  }
});

test("Wake Window Calculator static HTML table and chip show typical range matching schedule (#36)", () => {
  // Check static HTML table column header has "Typical wake window"
  assert.match(wwHtml, /<th[^>]*>\s*Typical wake window\s*<\/th>/i);

  // Check static HTML table row for 4 months has 1.5-2.5 h
  assert.match(
    wwHtml,
    /<th[^>]*>\s*4 months\s*<\/th>\s*<td[^>]*>\s*1\.5-2\.5 h\s*<\/td>/i
  );

  // Check guidance note labels ranges as typical
  assert.match(
    wwHtml,
    /these are typical ranges, not exact targets/i
  );
});

/* ========================================================================== */
/* Nap Transition Checker tests (#36)                                        */
/* ========================================================================== */

const napScript = extractMainScript(napHtml, /var PLANS/);

function createMockClassList() {
  const classes = new Set();
  return {
    add: (c) => classes.add(c),
    remove: (c) => classes.delete(c),
    contains: (c) => classes.has(c),
    toggle: (c) => {
      if (classes.has(c)) {
        classes.delete(c);
        return false;
      }
      classes.add(c);
      return true;
    }
  };
}

function createNapCheckerRuntime(initialData = {}) {
  const elements = {};
  const getEl = (id, tagName = "div") => {
    if (!elements[id]) {
      const el = {
        id,
        tagName: tagName.toUpperCase(),
        textContent: "",
        innerHTML: "",
        style: { display: "" },
        classList: createMockClassList(),
        listeners: {},
        children: [],
        appendChild(child) {
          this.children.push(child);
        },
        addEventListener(evt, fn) {
          if (!this.listeners[evt]) this.listeners[evt] = [];
          this.listeners[evt].push(fn);
        },
        dispatchEvent(evt) {
          const fns = this.listeners[evt] || [];
          for (const fn of fns) fn({ preventDefault() {} });
        },
        scrollIntoView() {}
      };
      elements[id] = el;
    }
    return elements[id];
  };

  // Pre-populate expected DOM elements
  const formEl = getEl("nap-quiz", "form");
  const resultBox = getEl("quiz-result", "section");
  resultBox.classList.add("hidden");
  getEl("result-verdict", "p");
  getEl("result-transition", "p");
  getEl("result-expect", "p");
  getEl("result-plan-heading", "p");
  getEl("result-steps", "ol");
  getEl("result-note", "p");
  const previewEl = getEl("result-preview", "div");
  previewEl.classList.add("hidden");

  let formDataValues = { ...initialData };

  class MockFormData {
    constructor() {}
    get(k) {
      return formDataValues[k] !== undefined ? formDataValues[k] : null;
    }
  }

  const docMock = {
    getElementById(id) {
      return getEl(id);
    },
    createElement(tagName) {
      return {
        tagName: tagName.toUpperCase(),
        textContent: "",
        innerHTML: ""
      };
    }
  };

  const sandbox = {
    document: docMock,
    FormData: MockFormData,
    console
  };

  const script = new vm.Script(napScript);
  const context = vm.createContext(sandbox);
  script.runInContext(context);

  return {
    elements,
    setFormData(newValues) {
      formDataValues = { ...formDataValues, ...newValues };
    },
    getFormData() {
      return { ...formDataValues };
    },
    submit() {
      formEl.dispatchEvent("submit");
    },
    change() {
      formEl.dispatchEvent("change");
    }
  };
}

test("Nap Transition Checker under 5 months: too-early verdict without primary drop-nap plan (#36)", () => {
  // Inputs: 3 or more naps, Under 5 months, fight=yes, bedtime=yes, twoweeks=yes
  const rt = createNapCheckerRuntime({
    naps: "3",
    age: "under5",
    fight: "yes",
    bedtime: "yes",
    twoweeks: "yes"
  });

  rt.submit();

  const elements = rt.elements;
  const resultBox = elements["quiz-result"];
  assert.equal(resultBox.classList.contains("hidden"), false, "Result box is visible");

  // Headline is keep-schedule message
  const verdict = elements["result-verdict"].textContent;
  assert.match(verdict, /Probably too early/i, "Verdict states probably too early");
  assert.match(verdict, /keep your current schedule/i, "Verdict headline advises keeping current schedule");

  // result-transition must NOT display "LIKELY TRANSITION"
  const transitionEl = elements["result-transition"];
  assert.equal(
    transitionEl.style.display,
    "none",
    "Likely transition label is hidden for too-early"
  );
  assert.equal(
    transitionEl.textContent,
    "",
    "Likely transition label text is cleared"
  );

  // Plan heading is "What to do now", not "Your plan"
  const planHeading = elements["result-plan-heading"].textContent;
  assert.equal(planHeading, "What to do now");

  // Primary steps are keep-schedule steps (protecting 3 naps), NOT drop-the-catnap plan
  const steps = elements["result-steps"].children.map((li) => li.textContent);
  assert.ok(steps.length > 0, "Steps list is populated");
  const joinedSteps = steps.join(" ");
  assert.match(joinedSteps, /Protect 3 naps/i, "Advises protecting 3 naps");
  assert.doesNotMatch(joinedSteps, /Cap the last catnap/i, "Primary steps must not be drop-catnap plan");

  // Later-age preview is clearly marked
  const previewEl = elements["result-preview"];
  assert.equal(previewEl.classList.contains("hidden"), false, "Preview section is shown");
  assert.match(previewEl.innerHTML, /Later-age preview/i, "Marked as later-age preview");
  assert.match(previewEl.innerHTML, /typical at 5-8 months/i, "Indicates typical age 5-8 months");
  assert.match(previewEl.innerHTML, /Future transition: 3 naps/i, "Identifies future transition");
});

test("Nap Transition Checker: changing answers replaces previous result in-place and preserves inputs (#36)", () => {
  const rt = createNapCheckerRuntime({
    naps: "3",
    age: "under5",
    fight: "yes",
    bedtime: "yes",
    twoweeks: "yes"
  });

  // First submit: under5 (too early)
  rt.submit();
  assert.match(rt.elements["result-verdict"].textContent, /Probably too early/i);
  assert.equal(rt.elements["result-plan-heading"].textContent, "What to do now");

  // Parent changes age to 5-8 months without resubmitting form
  rt.setFormData({ age: "5to8" });
  rt.change();

  // Result replaces previous result in-place
  assert.match(rt.elements["result-verdict"].textContent, /Ready/i);
  assert.equal(rt.elements["result-transition"].style.display, "");
  assert.match(rt.elements["result-transition"].textContent, /Likely transition: 3 naps -> 2 naps/i);
  assert.equal(rt.elements["result-plan-heading"].textContent, "Your plan");

  const steps = rt.elements["result-steps"].children.map((li) => li.textContent);
  const joinedSteps = steps.join(" ");
  assert.match(joinedSteps, /Cap the last catnap/i, "Ready path shows drop-catnap plan");
  assert.equal(rt.elements["result-preview"].classList.contains("hidden"), true, "Preview hidden when ready");

  // Inputs remain preserved in form state
  const data = rt.getFormData();
  assert.equal(data.naps, "3");
  assert.equal(data.age, "5to8");
  assert.equal(data.fight, "yes");
  assert.equal(data.bedtime, "yes");
  assert.equal(data.twoweeks, "yes");
});
