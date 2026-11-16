
(function () {
  const select = document.getElementById("view-select");
  const img = document.getElementById("main-image");
  const caption = document.getElementById("main-caption");
  if (!select || !img || typeof ATLAS_ASSETS === "undefined") return;
  select.addEventListener("change", function () {
    const key = select.value;
    const entry = ATLAS_ASSETS[key];
    if (!entry) return;
    img.src = entry.src;
    img.alt = entry.alt;
    if (caption) caption.textContent = entry.caption;
  });
})();
