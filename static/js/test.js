/* Assessment page: countdown timer, answered counter and progress bar */
(function () {
  const form = document.getElementById("test-form");
  if (!form) return;
  const total = form.querySelectorAll(".question").length;
  const bar = document.getElementById("progress-bar");
  const label = document.getElementById("answered");

  function update() {
    const done = new Set([...form.querySelectorAll("input[type=radio]:checked")].map((i) => i.name)).size;
    bar.style.width = (100 * done) / total + "%";
    label.textContent = done + " of " + total + " answered";
  }
  form.addEventListener("change", update);

  const timer = document.getElementById("timer");
  const out = document.getElementById("time-left");
  let left = parseInt(timer.dataset.minutes, 10) * 60;
  const tick = setInterval(() => {
    left -= 1;
    const m = Math.floor(left / 60), s = left % 60;
    out.textContent = m + ":" + String(s).padStart(2, "0");
    timer.classList.toggle("low", left <= 120);
    if (left <= 0) { clearInterval(tick); form.submit(); }  // auto-submit when time is up
  }, 1000);

  form.addEventListener("submit", (e) => {
    const done = new Set([...form.querySelectorAll("input[type=radio]:checked")].map((i) => i.name)).size;
    if (left > 0 && done < total &&
        !confirm((total - done) + " question(s) are unanswered and will count as wrong. Submit anyway?")) {
      e.preventDefault();
    }
  });
})();
