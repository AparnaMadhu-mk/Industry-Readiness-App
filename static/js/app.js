/* Upload wizard: 3 steps, drag & drop, client-side validation, loading overlay */
(function () {
  const form = document.getElementById("analyse-form");
  if (!form) return;

  const MAX = 5 * 1024 * 1024;
  const panels = [...form.querySelectorAll(".panel")];
  const steps = [...document.querySelectorAll(".steps li")];
  const fileInput = document.getElementById("cv");
  const dz = document.getElementById("dropzone");
  const chip = document.getElementById("file-chip");
  const errFile = document.getElementById("err-file");
  let current = 0;

  function show(i) {
    current = i;
    panels.forEach((p, n) => p.classList.toggle("active", n === i));
    steps.forEach((s, n) => {
      s.classList.toggle("active", n === i);
      s.classList.toggle("done", n < i);
    });
    if (i === 2) buildReview();
    window.scrollTo({ top: document.getElementById("analyse").offsetTop - 90, behavior: "smooth" });
  }

  function fileProblem(f) {
    if (!f) return "Please choose your CV first (PDF or DOCX).";
    const ext = f.name.split(".").pop().toLowerCase();
    if (!["pdf", "docx"].includes(ext)) return "Unsupported file type. Please upload a PDF or DOCX.";
    if (f.size > MAX) return "File is larger than the 5 MB limit.";
    if (f.size === 0) return "This file is empty.";
    return null;
  }

  function showFile() {
    const f = fileInput.files[0];
    const problem = f ? fileProblem(f) : null;
    errFile.hidden = !problem;
    errFile.textContent = problem || "";
    dz.classList.toggle("has-file", !!f && !problem);
    chip.hidden = !f;
    if (f) chip.textContent = "📎 " + f.name + " (" + (f.size / 1024).toFixed(0) + " KB)";
  }

  fileInput.addEventListener("change", showFile);
  ["dragenter", "dragover"].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((e) =>
    dz.addEventListener(e, (ev) => { ev.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (ev) => {
    if (ev.dataTransfer.files.length) {
      fileInput.files = ev.dataTransfer.files;
      showFile();
    }
  });

  form.querySelectorAll("[data-next]").forEach((b) =>
    b.addEventListener("click", () => {
      if (current === 0) {
        const problem = fileProblem(fileInput.files[0]);
        if (problem) { errFile.hidden = false; errFile.textContent = problem; return; }
      }
      show(Math.min(current + 1, panels.length - 1));
    }));
  form.querySelectorAll("[data-prev]").forEach((b) =>
    b.addEventListener("click", () => show(Math.max(current - 1, 0))));

  function buildReview() {
    const v = (id) => (document.getElementById(id).value || "").trim();
    const role = form.querySelector("input[name=role]:checked");
    const rows = [
      ["CV file", fileInput.files[0] ? fileInput.files[0].name : "-"],
      ["Target role", role ? role.nextElementSibling.textContent.trim().replace(/^\S+\s+/, "") : "-"],
      ["Name", v("name") || "Anonymous"],
      ["GitHub", v("github") || "not provided"],
      ["Portfolio", v("portfolio") || "not provided"],
      ["Deployed links", v("live_urls") || "not provided"],
    ];
    const box = document.getElementById("review");
    box.innerHTML = "";
    rows.forEach(([k, val]) => {
      const d = document.createElement("div");
      const b = document.createElement("b");
      b.textContent = k;
      const s = document.createElement("span");
      s.textContent = val;
      d.append(b, s);
      box.appendChild(d);
    });
  }

  form.addEventListener("submit", (ev) => {
    const problem = fileProblem(fileInput.files[0]);
    if (problem) { ev.preventDefault(); show(0); errFile.hidden = false; errFile.textContent = problem; return; }
    if (!document.getElementById("consent").checked) {
      ev.preventDefault();
      document.getElementById("err-consent").hidden = false;
      return;
    }
    const overlay = document.getElementById("loading");
    overlay.hidden = false;
    const items = [...overlay.querySelectorAll(".load-steps li")];
    items.forEach((li, i) => setTimeout(() => li.classList.add("on"), 500 + i * 1100));
  });

  // If the server sent back an error, jump to the first panel so the user sees it
  if (document.querySelector(".alert.error")) show(0);
})();
