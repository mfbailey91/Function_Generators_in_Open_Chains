(() => {
  const data = JSON.parse(document.getElementById('atlas-data').textContent);
  const sampleSelect = document.getElementById('sample-select');
  const viewSelect = document.getElementById('view-select');
  const out = document.getElementById('inspector');
  function render() {
    const row = data.rows.find(r => r.q_sample_id === sampleSelect.value
      && r.mechanism_id === 'fourbar') || data.rows[0];
    const view = viewSelect.value;
    const cap = row.capability;
    let value = null;
    if (view === 'isotropic_speed') value = cap.isotropic_speed;
    else if (cap.directional_ray_speed) value = cap.directional_ray_speed[view];
    const peers = data.rows.filter(r => r.q_sample_id === row.q_sample_id);
    out.innerHTML = '<pre>' + JSON.stringify({
      q_sample_id: row.q_sample_id,
      grid_index: row.grid_index,
      view, value,
      status_by_mechanism: Object.fromEntries(
        peers.map(p => [p.mechanism_id, p.capability.status])),
      primary_eligible: row.primary_eligible,
      directions: cap.directions,
      directional_support: cap.directional_support,
      directional_ray_speed: cap.directional_ray_speed,
      ik_positive_x: row.ik_positive_x
    }, null, 2) + '</pre>';
  }
  sampleSelect.addEventListener('change', render);
  viewSelect.addEventListener('change', render);
  render();
})();
