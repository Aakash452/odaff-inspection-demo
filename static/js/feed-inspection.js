/*
 * feed-inspection.js - behavior specific to CF-101.
 * Everything generic lives in form-core.js; this file only wires up
 * this form's parts and its business rules.
 */
(function () {
  "use strict";
  const K = window.FormKit;
  const form = document.getElementById("inspection-form");
  const summary = document.getElementById("error-summary");
  const statusEl = document.getElementById("submit-status");
  const submitBtn = document.getElementById("submit-btn");

  // ---- Repeating sections ----
  const repeaters = {
    samples: K.repeater(form.querySelector('[data-repeat="samples"]'),
      document.getElementById("tpl-sample"), { onChange: changed }),
    violations: K.repeater(form.querySelector('[data-repeat="violations"]'),
      document.getElementById("tpl-violation"), { onChange: changed }),
  };
  document.getElementById("add-sample").addEventListener("click", () => {
    repeaters.samples.add().querySelector("input").focus();
  });
  document.getElementById("add-violation").addEventListener("click", () => {
    repeaters.violations.add().querySelector("textarea").focus();
  });

  // ---- Signatures ----
  const pads = {};
  form.querySelectorAll("[data-sig]").forEach(box => {
    const pad = K.signaturePad(box.querySelector("canvas"));
    pads[box.dataset.sig] = pad;
    box.querySelector("[data-clear]").addEventListener("click", pad.clear);
    box.querySelector("canvas").addEventListener("signature", changed);
  });
  const refused = form.elements.rep_refused_to_sign;
  function syncRefused() {
    const box = form.querySelector('[data-sig="firm_rep_signature"]');
    box.classList.toggle("disabled", refused.checked);
    if (refused.checked) pads.firm_rep_signature.clear();
  }

  // ---- Checklist "No" -> matching violation in Part 4 ----
  const checkText = code => form.querySelector(`.check[data-code="${code}"] legend`).lastChild.textContent.trim();

  function violationFor(code) {
    return repeaters.violations.rows().find(r => r.querySelector('[data-field="item_code"]').value === code);
  }

  function onChecklist(code, answer) {
    form.querySelector(`.check[data-code="${code}"]`).classList.toggle("answered-no", answer === "No");
    const existing = violationFor(code);
    if (answer === "No" && !existing) {
      const prefill = `Item ${code} not met: ${checkText(code)}.`;
      const row = repeaters.violations.add({ item_code: code, description: prefill }, { prefill });
      tagRow(row, code);
      row.classList.add("flash");
      statusEl.textContent = `Violation added to Part 4 for item ${code}.`;
    } else if (answer !== "No" && existing) {
      // Remove the auto-added row only if the inspector has not worked on it.
      const untouched = existing.querySelector('[data-field="description"]').value === existing.dataset.prefill
        && !existing.querySelector('[data-field="corrective_action"]').value.trim();
      if (untouched) {
        repeaters.violations.remove(existing);
        statusEl.textContent = `Violation for item ${code} removed.`;
      }
    }
  }

  function tagRow(row, code) {
    const tag = row.querySelector("[data-item-tag]");
    tag.textContent = `From item ${code}`;
    tag.hidden = false;
  }

  // ---- Form-specific rules that HTML attributes cannot express ----
  function businessRules() {
    const e = {};
    const v = name => K.fieldValue(form, name);
    const today = new Date(); today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
    if (v("inspection_date") && v("inspection_date") > today.toISOString().slice(0, 10)) {
      e.inspection_date = "Inspection date cannot be in the future.";
    }
    if (v("time_in") && v("time_out") && v("time_out") < v("time_in")) {
      e.time_out = "Time out must be after time in.";
    }
    form.querySelectorAll(".check:not([hidden])").forEach(box => {
      const code = box.dataset.code;
      if (v(`checklist.${code}`) === "No" && !violationFor(code)) {
        e[`checklist.${code}`] = `Item ${code} is marked No. Add a violation for it in Part 4.`;
      }
    });
    repeaters.violations.values().forEach((row, i) => {
      if (row.correct_by && v("inspection_date") && row.correct_by < v("inspection_date")) {
        e[`violations[${i}].correct_by`] = "Correct-by date must be on or after the inspection date.";
      }
    });
    if (pads.inspector_signature.isEmpty()) e.inspector_signature = "Inspector signature is required.";
    if (refused.checked) {
      if (!v("remarks")) e.remarks = "Note in remarks that the representative refused to sign.";
    } else if (pads.firm_rep_signature.isEmpty()) {
      e.firm_rep_signature = "Firm representative signature is required, or check 'Refused to sign'.";
    }
    return e;
  }

  // ---- Payload sent to POST /api/inspections ----
  function payload() {
    const checklist = {};
    form.querySelectorAll(".check:not([hidden])").forEach(box => {
      const val = K.fieldValue(form, `checklist.${box.dataset.code}`);
      if (val) checklist[box.dataset.code] = val;
    });
    return {
      ...K.scalarValues(form),
      samples: repeaters.samples.values(),
      checklist,
      violations: repeaters.violations.values(),
      inspector_signature: pads.inspector_signature.toDataURL(),
      firm_rep_signature: refused.checked ? null : pads.firm_rep_signature.toDataURL(),
    };
  }

  // ---- Part tracker status ----
  const partLinks = [...document.querySelectorAll(".tracker a")];
  function updateTracker(errors = null) {
    document.querySelectorAll(".part").forEach(part => {
      const link = partLinks.find(a => a.dataset.part === part.dataset.part);
      const fields = [...part.querySelectorAll("input, select, textarea")].filter(f => !f.disabled && f.type !== "hidden");
      let ok = fields.every(f => f.checkValidity());
      if (part.dataset.part === "5") ok = ok && !pads.inspector_signature.isEmpty() && (refused.checked || !pads.firm_rep_signature.isEmpty());
      link.classList.toggle("complete", ok);
      if (errors) {
        const bad = Object.keys(errors).some(p => {
          const el = document.getElementById(`f-${p.replace(/[^\w]/g, "-")}`);
          return el && part.contains(el);
        });
        link.classList.toggle("has-error", bad);
      }
    });
    const n = repeaters.samples.rows().length;
    const official = repeaters.samples.values().filter(s => s.sample_type === "Official").length;
    document.getElementById("sample-tally").textContent = n ? `${n} sample${n > 1 ? "s" : ""}, ${official} official` : "";
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (en.isIntersecting) partLinks.forEach(a => a.classList.toggle("current", a.dataset.part === en.target.dataset.part));
    });
  }, { rootMargin: "-40% 0px -55% 0px" });
  document.querySelectorAll(".part").forEach(p => observer.observe(p));

  // ---- Draft autosave ----
  const drafts = K.draft("cf101-draft", () => {
    const p = payload();
    p.violation_prefills = repeaters.violations.rows().map(r => r.dataset.prefill || "");
    return p;
  }, state => {
    K.setScalars(form, state);
    Object.entries(state.checklist || {}).forEach(([code, val]) => {
      const radio = form.querySelector(`[name="checklist.${code}"][value="${val}"]`);
      if (radio) radio.checked = true;
      form.querySelector(`.check[data-code="${code}"]`)?.classList.toggle("answered-no", val === "No");
    });
    (state.samples || []).forEach(s => repeaters.samples.add(s));
    (state.violations || []).forEach((v, i) => {
      const pre = (state.violation_prefills || [])[i];
      const row = repeaters.violations.add(v, pre ? { prefill: pre } : {});
      if (v.item_code) tagRow(row, v.item_code);
    });
    if (state.inspector_signature) pads.inspector_signature.load(state.inspector_signature);
    if (state.firm_rep_signature) pads.firm_rep_signature.load(state.firm_rep_signature);
  }, document.getElementById("draft-status"));

  function changed() {
    K.applyConditionals(form);
    updateTracker();
    drafts.save();
  }

  form.addEventListener("input", changed);
  form.addEventListener("change", e => {
    if (e.target.name?.startsWith("checklist.")) onChecklist(e.target.name.split(".")[1], e.target.value);
    if (e.target === refused) syncRefused();
    changed();
  });

  // ---- Submit ----
  form.addEventListener("submit", async e => {
    e.preventDefault();
    K.applyConditionals(form);
    const errors = { ...K.collectErrors(form, repeaters), ...businessRules() };
    if (Object.keys(errors).length) {
      K.showErrors(form, errors, summary, repeaters);
      updateTracker(errors);
      statusEl.textContent = `${Object.keys(errors).length} item${Object.keys(errors).length > 1 ? "s" : ""} to fix.`;
      return;
    }
    K.clearErrors(form, summary);
    submitBtn.disabled = true;
    statusEl.textContent = "Saving inspection and creating the PDF...";
    try {
      const res = await fetch("/api/inspections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      const body = await res.json();
      if (res.status === 422) {
        K.showErrors(form, body.errors, summary, repeaters);
        updateTracker(body.errors);
        statusEl.textContent = "The server found items to fix.";
        return;
      }
      if (!res.ok) throw new Error(body.errors?._form || "Save failed.");
      drafts.discard();
      form.hidden = true;
      document.querySelector(".tracker").hidden = true;
      const done = document.getElementById("done");
      document.getElementById("done-number").textContent = body.number;
      const link = document.getElementById("done-pdf");
      if (body.pdf_url) link.href = body.pdf_url; else link.hidden = true;
      done.hidden = false;
      done.focus();
    } catch (err) {
      statusEl.textContent = `${err.message} Your entries are saved on this device. Try again when you have a connection.`;
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.getElementById("done-new").addEventListener("click", () => location.reload());

  // ---- Start: restore a draft or prefill today's date and time ----
  const savedAt = drafts.load();
  if (savedAt) {
    document.getElementById("draft-banner-text").textContent =
      `Draft from ${new Date(savedAt).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} restored.`;
    document.getElementById("draft-banner").hidden = false;
  } else {
    const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    form.elements.inspection_date.value = now.toISOString().slice(0, 10);
    form.elements.time_in.value = now.toISOString().slice(11, 16);
  }
  document.getElementById("draft-discard").addEventListener("click", () => {
    drafts.discard();
    location.reload();
  });
  syncRefused();
  K.applyConditionals(form);
  updateTracker();
})();
