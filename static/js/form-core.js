/*
 * form-core.js - reusable pieces for every converted inspection form.
 *
 * Nothing in here knows about feed inspections. Each of the ~70 forms
 * loads this file plus one small form-specific script, so repeating
 * rows, conditional fields, signatures, validation, drafts and submit
 * behave the same everywhere and are written (and fixed) once.
 */
(function (global) {
  "use strict";

  // ---------- Repeating rows (samples, violations, line items...) ----------
  function repeater(container, template, opts = {}) {
    const onChange = opts.onChange || (() => {});

    function renumber() {
      container.querySelectorAll(":scope > .row").forEach((row, i) => {
        row.querySelectorAll("[data-row-number]").forEach(el => { el.textContent = i + 1; });
      });
    }

    function add(values = {}, meta = {}) {
      const row = template.content.firstElementChild.cloneNode(true);
      Object.entries(values).forEach(([k, v]) => {
        const input = row.querySelector(`[data-field="${k}"]`);
        if (input && v != null) input.value = v;
      });
      Object.entries(meta).forEach(([k, v]) => { row.dataset[k] = v; });
      row.querySelector("[data-remove]")?.addEventListener("click", () => remove(row));
      container.appendChild(row);
      renumber();
      onChange();
      return row;
    }

    function remove(row) {
      row.remove();
      renumber();
      onChange();
    }

    function rows() { return [...container.querySelectorAll(":scope > .row")]; }

    function values() {
      return rows().map(row => {
        const out = {};
        row.querySelectorAll("[data-field]").forEach(el => { out[el.dataset.field] = el.value.trim(); });
        return out;
      });
    }

    function clear() { rows().forEach(r => r.remove()); onChange(); }

    return { add, remove, rows, values, clear, name: container.dataset.repeat };
  }

  // ---------- Conditional fields: data-show-when="field:valueA|valueB" ----------
  function fieldValue(form, name) {
    const els = form.querySelectorAll(`[name="${name}"]`);
    if (!els.length) return "";
    const first = els[0];
    if (first.type === "checkbox") return first.checked ? first.value : "";
    if (first.type === "radio") return [...els].find(e => e.checked)?.value || "";
    return first.value;
  }

  function applyConditionals(form) {
    form.querySelectorAll("[data-show-when]").forEach(el => {
      const [field, list] = el.dataset.showWhen.split(":");
      const show = list.split("|").includes(fieldValue(form, field));
      el.hidden = !show;
      // Hidden inputs are disabled so they are skipped by validation and serialize().
      el.querySelectorAll("input, select, textarea").forEach(i => { i.disabled = !show; });
    });
  }

  // ---------- Signature pad (pointer events: finger, stylus, mouse) ----------
  function signaturePad(canvas) {
    const ctx = canvas.getContext("2d");
    let drawing = false, empty = true, last = null;

    function resize() {
      const data = empty ? null : canvas.toDataURL();
      const ratio = Math.max(window.devicePixelRatio || 1, 1);
      canvas.width = canvas.offsetWidth * ratio;
      canvas.height = canvas.offsetHeight * ratio;
      ctx.scale(ratio, ratio);
      ctx.lineWidth = 2.2; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = "#1F2A22";
      if (data) load(data);
    }

    function point(e) {
      const r = canvas.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    }

    canvas.addEventListener("pointerdown", e => {
      drawing = true; last = point(e); canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointermove", e => {
      if (!drawing) return;
      const p = point(e);
      ctx.beginPath(); ctx.moveTo(last.x, last.y); ctx.lineTo(p.x, p.y); ctx.stroke();
      last = p;
      if (empty) { empty = false; canvas.dispatchEvent(new Event("signature")); }
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach(t =>
      canvas.addEventListener(t, () => {
        if (drawing) canvas.dispatchEvent(new Event("signature"));
        drawing = false;
      }));

    function clear() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      empty = true;
      canvas.dispatchEvent(new Event("signature"));
    }

    function load(dataUrl) {
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.offsetWidth, canvas.offsetHeight);
        empty = false;
        canvas.dispatchEvent(new Event("signature"));
      };
      img.src = dataUrl;
    }

    window.addEventListener("resize", resize);
    resize();
    return { clear, load, isEmpty: () => empty, toDataURL: () => (empty ? null : canvas.toDataURL("image/png")) };
  }

  // ---------- Field paths: "firm_name", "checklist.L2", "samples[0].guarantor" ----------
  function findField(form, path, repeaters) {
    const m = path.match(/^(\w+)\[(\d+)\]\.(\w+)$/);
    if (m) {
      const rep = repeaters[m[1]];
      return rep?.rows()[Number(m[2])]?.querySelector(`[data-field="${m[3]}"]`) || null;
    }
    if (path.startsWith("checklist.")) {
      return form.querySelector(`.check[data-code="${path.split(".")[1]}"]`);
    }
    return form.querySelector(`[name="${path}"]`) || form.querySelector(`[data-sig="${path}"]`);
  }

  function labelFor(el) {
    if (!el) return "Form";
    if (el.matches(".check")) return `Item ${el.dataset.code}`;
    if (el.matches(".sig")) return el.querySelector(".sig-label").textContent.trim();
    const lbl = el.closest("label")?.querySelector(".lbl");
    const text = lbl ? lbl.firstChild.textContent.trim() : el.name;
    const row = el.closest(".row");
    return row ? `${row.querySelector("legend").textContent.trim().split("\n")[0]}: ${text}` : text;
  }

  // ---------- Client-side validation (HTML constraints + form-specific rules) ----------
  function messageFor(el) {
    const v = el.validity;
    if (v.valueMissing) return el.type === "radio" ? "Choose an answer." : "This field is required.";
    if (v.patternMismatch) return el.dataset.msgPattern || "Check the format.";
    if (v.rangeUnderflow) return `Must be ${el.min} or more.`;
    if (v.rangeOverflow) return `Must be ${el.max} or less.`;
    if (v.stepMismatch) return "Enter a whole number.";
    if (v.badInput) return "Enter a number.";
    return el.validationMessage;
  }

  function collectErrors(form, repeaters) {
    const errors = {};
    form.querySelectorAll("input, select, textarea").forEach(el => {
      if (el.disabled || el.type === "hidden" || el.checkValidity()) return;
      const path = pathOf(el, repeaters);
      if (!errors[path]) errors[path] = messageFor(el);
    });
    return errors;
  }

  function pathOf(el, repeaters) {
    if (el.dataset.field) {
      const row = el.closest(".row");
      const rep = Object.values(repeaters).find(r => r.rows().includes(row));
      return `${rep.name}[${rep.rows().indexOf(row)}].${el.dataset.field}`;
    }
    return el.name;
  }

  function clearErrors(form, summary) {
    form.querySelectorAll(".invalid").forEach(el => el.classList.remove("invalid"));
    form.querySelectorAll(".err").forEach(el => el.remove());
    form.querySelectorAll("[aria-invalid]").forEach(el => el.removeAttribute("aria-invalid"));
    summary.hidden = true;
    summary.querySelector("ul").innerHTML = "";
  }

  function showErrors(form, errors, summary, repeaters) {
    clearErrors(form, summary);
    const list = summary.querySelector("ul");
    let n = 0;
    Object.entries(errors).forEach(([path, msg]) => {
      const el = path === "_form" ? null : findField(form, path, repeaters);
      const li = document.createElement("li");
      if (el) {
        const id = el.id || (el.id = `f-${path.replace(/[^\w]/g, "-")}`);
        el.classList.add("invalid");
        el.setAttribute("aria-invalid", "true");
        const note = document.createElement("span");
        note.className = "err"; note.textContent = msg;
        (el.matches(".check, .sig") ? el : el.closest("label") || el).appendChild(note);
        const a = document.createElement("a");
        a.href = `#${id}`; a.textContent = `${labelFor(el)}: ${msg}`;
        a.addEventListener("click", e => { e.preventDefault(); el.scrollIntoView({ block: "center" }); (el.querySelector?.("input") || el).focus?.(); });
        li.appendChild(a);
      } else {
        li.textContent = msg;
      }
      list.appendChild(li); n++;
    });
    summary.hidden = n === 0;
    if (n) { summary.focus(); summary.scrollIntoView({ block: "start" }); }
  }

  // ---------- Draft autosave: field connectivity is unreliable ----------
  function draft(key, getState, setState, statusEl) {
    let timer = null;
    return {
      save() {
        clearTimeout(timer);
        timer = setTimeout(() => {
          try {
            localStorage.setItem(key, JSON.stringify({ savedAt: Date.now(), state: getState() }));
            if (statusEl) statusEl.textContent = `Draft saved ${new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
          } catch (_) { /* storage full or disabled: the form still works */ }
        }, 600);
      },
      load() {
        try {
          const raw = localStorage.getItem(key);
          if (!raw) return null;
          const d = JSON.parse(raw);
          setState(d.state);
          return d.savedAt;
        } catch (_) { return null; }
      },
      discard() { try { localStorage.removeItem(key); } catch (_) {} if (statusEl) statusEl.textContent = ""; },
    };
  }

  // ---------- Simple scalar fields <-> object ----------
  function scalarValues(form) {
    const out = {};
    form.querySelectorAll("[name]").forEach(el => {
      if (el.disabled || el.name.includes(".")) return;
      if (el.type === "checkbox") out[el.name] = el.checked;
      else if (el.type === "radio") { if (el.checked) out[el.name] = el.value; }
      else out[el.name] = el.value.trim();
    });
    return out;
  }

  function setScalars(form, data) {
    Object.entries(data || {}).forEach(([name, v]) => {
      const els = form.querySelectorAll(`[name="${name}"]`);
      els.forEach(el => {
        if (el.type === "checkbox") el.checked = !!v;
        else if (el.type === "radio") el.checked = el.value === v;
        else el.value = v ?? "";
      });
    });
  }

  global.FormKit = { repeater, applyConditionals, signaturePad, collectErrors, showErrors, clearErrors, draft, scalarValues, setScalars, fieldValue };
})(window);
