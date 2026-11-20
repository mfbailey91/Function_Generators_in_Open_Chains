
(function () {
  "use strict";
  const dataElement = document.getElementById("atlas-data");
  const viewSelect = document.getElementById("view-select");
  const cellSelect = document.getElementById("cell-select");
  if (!dataElement || !viewSelect || !cellSelect) return;
  const data = JSON.parse(dataElement.textContent);
  const image = document.getElementById("main-image");
  const caption = document.getElementById("main-caption");
  const readout = document.getElementById("cell-readout");
  const panels = document.getElementById("selected-polygons");
  const comparison = document.getElementById("cell-comparison");
  const identity = document.getElementById("selected-identity");
  const svgNS = "http://www.w3.org/2000/svg";

  function appendText(parent, tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    parent.appendChild(node);
    return node;
  }
  function svgNode(parent, tag, attrs, text) {
    const node = document.createElementNS(svgNS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    parent.appendChild(node);
    return node;
  }
  function numberText(value) {
    return value === null || value === undefined
      ? "unavailable" : Number(value).toPrecision(6);
  }
  function displayedField(row) {
    const direction = row.directional_fields &&
      row.directional_fields[viewSelect.value];
    return direction || row.isotropic_radius_field;
  }
  function drawStoredPolygon(parent, row, bounds) {
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", "0 0 330 320");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label",
      row.mechanism_id + " stored force polygon on common axes");
    parent.appendChild(svg);
    const [lo, hi] = bounds.xlim;
    // Only a display-coordinate transform of stored vertices; no scientific
    // map, rank, capacity, direction, or comparison is evaluated in the browser.
    const px = value => 50 + 240 * (value - lo) / (hi - lo);
    const py = value => 20 + 240 * (hi - value) / (hi - lo);
    svgNode(svg, "rect",
      {x:50, y:20, width:240, height:240, fill:"white", stroke:"#888"});
    svgNode(svg, "line", {x1:px(0), y1:20, x2:px(0), y2:260, stroke:"#bbb"});
    svgNode(svg, "line", {x1:50, y1:py(0), x2:290, y2:py(0), stroke:"#bbb"});
    svgNode(svg, "text", {x:50, y:278, "text-anchor":"start"}, numberText(lo));
    svgNode(svg, "text", {x:290, y:278, "text-anchor":"end"}, numberText(hi));
    svgNode(svg, "text", {x:45, y:25, "text-anchor":"end"}, numberText(hi));
    svgNode(svg, "text", {x:45, y:260, "text-anchor":"end"}, numberText(lo));
    svgNode(svg, "text", {x:170, y:303, "text-anchor":"middle"},
      "Fx (normalized torque/length)");
    svgNode(svg, "text",
      {x:9, y:150, transform:"rotate(-90 9 150)", "text-anchor":"middle"}, "Fy");
    if (row.vertices && row.vertices.length) {
      svgNode(svg, "polygon", {
        points: row.vertices.map(vertex =>
          px(vertex[0]) + "," + py(vertex[1])).join(" "),
        fill:"#1d4f9122", stroke:"#1d4f91", "stroke-width":1.5
      });
    } else {
      svgNode(svg, "text", {x:170, y:135, "text-anchor":"middle"}, "No closed polygon");
      svgNode(svg, "text", {x:170, y:155, "text-anchor":"middle"}, row.status);
    }
  }
  function renderCell() {
    const cell = data.cells[cellSelect.value];
    if (!cell) return;
    identity.textContent = "Grid (" + cell.grid_index.join(", ") + ") · " +
      cell.q_sample_id;
    if (viewSelect.value === "true_scale_detail" && caption) {
      caption.textContent = "Selected-cell true-scale polygons below: " +
        cell.q_sample_id + ". All three panels share the stored force bounds.";
    }
    panels.replaceChildren();
    Object.values(cell.arms).forEach(row => {
      const panel = document.createElement("section");
      panels.appendChild(panel);
      appendText(panel, "h3", row.mechanism_id);
      appendText(panel, "p", "Whole-set status: " + row.status, "status-label");
      const field = displayedField(row);
      const fieldName = row.directional_fields &&
        row.directional_fields[viewSelect.value]
        ? viewSelect.value + " ray" : "isotropic radius";
      appendText(panel, "p",
        fieldName + ": " + numberText(field.value) + " · " + field.status);
      appendText(panel, "p",
        "Unit actuator-effort box: " + JSON.stringify(row.torque_limits));
      if (row.status !== "regular") {
        appendText(panel, "p",
          "Diagnostic state; excluded from regular-only primary comparisons.",
          "warning");
      }
      if (row.low_gain_warning) {
        appendText(panel, "p",
          "Low-gain warning: inspect source rank reports.", "warning");
      }
      if (row.vertex_feasibility && !row.vertex_feasibility.ok) {
        appendText(panel, "p",
          "Unit-box corner residual exceeds tolerance; inspect diagnostics.",
          "warning");
      }
      drawStoredPolygon(panel, row, cell.force_bounds);
    });
    const fieldKey = cell.comparisons[viewSelect.value]
      ? viewSelect.value : "isotropic_radius";
    comparison.textContent = "Stored paired comparison (" + fieldKey + "):\n" +
      JSON.stringify(cell.comparisons[fieldKey] || null, null, 2);
    readout.textContent = JSON.stringify(
      {selected_view:viewSelect.value, ...cell}, null, 2);
  }
  function renderView() {
    const asset = data.assets[viewSelect.value];
    if (asset && image) {
      image.hidden = viewSelect.value === "true_scale_detail";
      image.src = asset.src;
      image.alt = asset.alt;
      if (caption) caption.textContent = asset.caption;
    }
    renderCell();
  }
  viewSelect.addEventListener("change", renderView);
  cellSelect.addEventListener("change", renderCell);
  renderView();
})();
