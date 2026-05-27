const API = 'http://localhost:5000';

// ── Map init ───────────────────────────────────────────────────────
const map = L.map('map', { attributionControl: false, zoomControl: false })
  .setView([51.2538, -85.3232], 6);

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  subdomains: 'abcd', maxZoom: 19
}).addTo(map);

L.control.zoom({ position: 'bottomright' }).addTo(map);

// ── Layer state ────────────────────────────────────────────────────
let markers = L.layerGroup().addTo(map);
let turbinesVisible = true;


let windOverlay = null,        windVisible = false;
let resLayer = null,           resVisible = false;
let roadsLayer = null,         roadsVisible = false;
let protectedLayer = null,     protectedVisible = false;
let hydroStationLayer = null,  hydroStationZones = null,  hydroStationsVisible = false;
let hydroLineLayer = null,     hydroLineZones = null,     hydroLinesVisible = false;
let topSitesLayer = null,      topSitesVisible = false;
let lakesLayer = null,         lakesVisible = false;
let turbineBufferLayer = null, turbineBufferVisible = false;

// ── Helpers ────────────────────────────────────────────────────────
function setTog(id, on) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle('on', on);
}

function darkTip(text) {
  return `<span style="font-family:ui-monospace,monospace;font-size:11px;color:rgba(255,255,255,0.85)">${text}</span>`;
}

function zoneStyle(lbl, exc, gd, mod, poor) {
  if (lbl.includes('Excellent')) return exc;
  if (lbl.includes('Good'))      return gd;
  if (lbl.includes('Moderate'))  return mod;
  if (lbl.includes('Poor'))      return poor;
  return { color: '#666', fillColor: '#666', fillOpacity: 0.08, weight: 0.8 };
}

const SZ = c => ({ color: c, fillColor: c, fillOpacity: 0.12, weight: 1 });

// ── Popup builders ─────────────────────────────────────────────────
function row(k, v, cls = '') {
  return `<div class="pc-row"><span class="pk">${k}</span><span class="pv ${cls}">${v}</span></div>`;
}

function scoreTier(score) {
  if (score >= 70) return ['exc', 'Excellent'];
  if (score >= 50) return ['gd',  'Good'];
  return ['fr', 'Fair'];
}

function buildCandidatePopup(p, rank) {
  const turbineCost = Math.round(3.5 * 1_000_000);
  const roadCost    = Math.round((p.dist_road_km  ?? 0) * 62_000);
  const gridCost    = Math.round((p.dist_hydro_km ?? 0) * 200_000);
  const subtotal    = turbineCost + roadCost + gridCost;
  const soft        = Math.round(subtotal * 0.15);
  const total       = subtotal + soft;

  const [tierCls, tierLbl] = scoreTier(p.final_score);
  const scoreCol = p.final_score >= 70 ? 'cg' : p.final_score >= 50 ? 'cm' : 'cb';
  const lat = p.lat ?? null;
  const lon = p.lon ?? null;

  return `<div class="pc">
    <div class="pc-head">
      <div class="pc-rank">${rank}</div>
      <span class="pc-heading">Candidate Site #${rank}</span>
      <span class="pc-tier ${tierCls}">${tierLbl}</span>
    </div>
    <div class="pc-rows">
      ${row('Final score',    p.final_score?.toFixed(1),   scoreCol)}
      ${row('ML score',       p.ml_score?.toFixed(3))}
      ${row('Wind speed',     (p.wind_speed?.toFixed(1)  ?? '—') + ' m/s')}
      ${row('Dist. to road',  (p.dist_road_km?.toFixed(1) ?? '—') + ' km')}
      ${row('Dist. to hydro', (p.dist_hydro_km?.toFixed(1) ?? '—') + ' km')}
    </div>
    <hr class="pc-div"/>
    <div class="pc-cost-lbl">Estimated cost · 3.5 MW</div>
    <div class="pc-rows">
      ${row('Turbine',         '$' + turbineCost.toLocaleString())}
      ${row('Road access',     '$' + roadCost.toLocaleString())}
      ${row('Grid connection', '$' + gridCost.toLocaleString())}
      ${row('Soft costs (15%)', '$' + soft.toLocaleString())}
    </div>
    <div class="pc-total">Total: $${total.toLocaleString()}</div>
    ${lat != null ? `<div class="pc-coords">${lat.toFixed(5)}° N  ${Math.abs(lon).toFixed(5)}° W</div>` : ''}
  </div>`;
}

function buildSimplePopup(title, pairs) {
  const rows = pairs.map(([k, v]) => row(k, v ?? '—')).join('');
  return `<div class="pc">
    <div class="pc-head"><span class="pc-heading">${title}</span></div>
    <div class="pc-rows">${rows}</div>
  </div>`;
}

function buildTurbinePopup(props) {
  const rows = Object.entries(props)
    .filter(([k]) => k !== 'geometry')
    .slice(0, 12)
    .map(([k, v]) => row(k.replace(/_/g, ' '), v ?? '—'))
    .join('');
  return `<div class="pc">
    <div class="pc-head"><span class="pc-heading" style="font-size:16px;font-weight:700;color:#fff">Existing Turbine</span></div>
    <div class="pc-rows">${rows}</div>
  </div>`;
}

// ── Candidate site icon ────────────────────────────────────────────
function makeCsIcon(rank, score) {
  const cls = score >= 70 ? 'hi' : score < 50 ? 'lo' : '';
  return L.divIcon({
    className: '',
    html: `<div class="cs-wrap">
             <div class="cs-glow"></div>
             <div class="cs-circle ${cls}">${rank}</div>
           </div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -18]
  });
}


// ── Turbine buffer ─────────────────────────────────────────────────
fetch(`${API}/api/turbine-buffer`)
  .then(r => r.json())
  .then(geo => {
    turbineBufferLayer = L.geoJSON(geo, {
      style: { color: '#9B59B6', fillColor: '#C39BD3', fillOpacity: 0.18, weight: 1 }
    });
    document.getElementById('turbine-buffer-toggle').disabled = false;
  });

document.getElementById('turbine-buffer-toggle').addEventListener('click', () => {
  if (!turbineBufferLayer) return;
  turbineBufferVisible = !turbineBufferVisible;
  turbineBufferVisible ? turbineBufferLayer.addTo(map) : map.removeLayer(turbineBufferLayer);
  setTog('turbine-buffer-toggle', turbineBufferVisible);
});

// ── Wind overlay ───────────────────────────────────────────────────
fetch(`${API}/api/wind-overlay`)
  .then(r => r.json())
  .then(meta => {
    windOverlay = L.imageOverlay(`${API}/api/wind-overlay/image`, meta.bounds, {
      opacity: 0.82, interactive: false
    });
  });

document.getElementById('wind-toggle').addEventListener('click', () => {
  if (!windOverlay) return;
  windVisible = !windVisible;
  windVisible ? windOverlay.addTo(map) : map.removeLayer(windOverlay);
  setTog('wind-toggle', windVisible);
});

// ── Residential buffer ─────────────────────────────────────────────
fetch(`${API}/api/residential-buffer`)
  .then(r => r.json())
  .then(geo => {
    resLayer = L.geoJSON(geo, {
      style: { color: '#888', fillColor: '#B4B2A9', fillOpacity: 0.22, weight: 0.6 }
    });
  });

document.getElementById('res-toggle').addEventListener('click', () => {
  if (!resLayer) return;
  resVisible = !resVisible;
  resVisible ? resLayer.addTo(map) : map.removeLayer(resLayer);
  setTog('res-toggle', resVisible);
});

// ── Roads ──────────────────────────────────────────────────────────
const ROAD_STYLE = {
  Freeway:                { color: '#aaa', weight: 1.2, opacity: 0.55 },
  'Expressway / Highway': { color: '#888', weight: 0.9, opacity: 0.5  },
  Arterial:               { color: '#666', weight: 0.6, opacity: 0.4  }
};

fetch(`${API}/api/roads`)
  .then(r => r.json())
  .then(geo => {
    roadsLayer = L.geoJSON(geo, {
      style: f => ROAD_STYLE[f.properties.road_class] || { color: '#555', weight: 0.5, opacity: 0.35 }
    });
  });

document.getElementById('roads-toggle').addEventListener('click', () => {
  if (!roadsLayer) return;
  roadsVisible = !roadsVisible;
  roadsVisible ? roadsLayer.addTo(map) : map.removeLayer(roadsLayer);
  setTog('roads-toggle', roadsVisible);
});

// ── Protected areas ────────────────────────────────────────────────
const PROT_STYLE = {
  Greenbelt:              { color: '#5DCAA5', fillColor: '#5DCAA5', weight: 0.8, fillOpacity: 0.18 },
  'Conservation Reserve': { color: '#993556', fillColor: '#993556', weight: 0.8, fillOpacity: 0.18 },
  'Provincial Park':      { color: '#D4537E', fillColor: '#D4537E', weight: 0.8, fillOpacity: 0.2  }
};

fetch(`${API}/api/protected-areas`)
  .then(r => r.json())
  .then(geo => {
    protectedLayer = L.geoJSON(geo, {
      style: f => PROT_STYLE[f.properties.protected_type] ||
        { color: '#888', fillColor: '#888', weight: 0.8, fillOpacity: 0.14 }
    });
  });

document.getElementById('protected-toggle').addEventListener('click', () => {
  if (!protectedLayer) return;
  protectedVisible = !protectedVisible;
  protectedVisible ? protectedLayer.addTo(map) : map.removeLayer(protectedLayer);
  setTog('protected-toggle', protectedVisible);
});

// ── Hydro stations + zones ─────────────────────────────────────────
const LINE_COLOURS = {
  'Hydro Line':                '#378ADD',
  'Unknown Transmission Line': '#185FA5',
  'Submerged Hydro Line':      '#33a02c'
};

Promise.all([
  fetch(`${API}/api/hydro-stations`).then(r => r.json()),
  fetch(`${API}/api/hydro-station-zones`).then(r => r.json()),
  fetch(`${API}/api/hydro-lines`).then(r => r.json()),
  fetch(`${API}/api/hydro-line-zones`).then(r => r.json())
]).then(([stPts, stZones, lineGeo, lineZones]) => {

  hydroStationZones = L.geoJSON(stZones, {
    style: f => zoneStyle(f.properties.label || '',
      SZ('#1a9641'), SZ('#EF9F27'), SZ('#d7191c'), SZ('#4A1820')),
    onEachFeature: (f, l) => l.bindTooltip(darkTip(f.properties.label))
  });

  hydroStationLayer = L.geoJSON(stPts, {
    pointToLayer: (f, ll) => L.circleMarker(ll, {
      radius: 5, color: '#185FA5', fillColor: '#378ADD', fillOpacity: 1, weight: 1.5
    }),
    onEachFeature: (f, l) => {
      const name = f.properties.GEOG_UNIT_DESCR || 'Hydro Station';
      l.bindTooltip(darkTip(name))
       .bindPopup(buildSimplePopup('Hydro Substation', [['Name', name]]), { maxWidth: 260 });
    }
  });

  hydroLineZones = L.geoJSON(lineZones, {
    style: f => zoneStyle(f.properties.label || '',
      SZ('#1a9641'), SZ('#EF9F27'), SZ('#d7191c'), SZ('#4A1820')),
    onEachFeature: (f, l) => l.bindTooltip(darkTip(f.properties.label))
  });

  hydroLineLayer = L.geoJSON(lineGeo, {
    style: f => ({
      color: LINE_COLOURS[f.properties.CLASS_SUBTYPE] || '#4A90D9',
      weight: 1.2, opacity: 0.75, dashArray: '5,4'
    }),
    onEachFeature: (f, l) => {
      const desc = f.properties.GEOG_UNIT_DESCR || f.properties.CLASS_SUBTYPE || '';
      l.bindTooltip(darkTip(desc));
    }
  });
});

document.getElementById('hydro-stations-toggle').addEventListener('click', () => {
  if (!hydroStationLayer) return;
  hydroStationsVisible = !hydroStationsVisible;
  if (hydroStationsVisible) { hydroStationZones.addTo(map); hydroStationLayer.addTo(map); }
  else { map.removeLayer(hydroStationZones); map.removeLayer(hydroStationLayer); }
  setTog('hydro-stations-toggle', hydroStationsVisible);
});

document.getElementById('hydro-lines-toggle').addEventListener('click', () => {
  if (!hydroLineLayer) return;
  hydroLinesVisible = !hydroLinesVisible;
  if (hydroLinesVisible) { hydroLineZones.addTo(map); hydroLineLayer.addTo(map); }
  else { map.removeLayer(hydroLineZones); map.removeLayer(hydroLineLayer); }
  setTog('hydro-lines-toggle', hydroLinesVisible);
});

// ── Top candidate sites ────────────────────────────────────────────
fetch(`${API}/api/top-sites`)
  .then(r => r.json())
  .then(geo => {
    const feats = [...geo.features].sort(
      (a, b) => (b.properties.final_score || 0) - (a.properties.final_score || 0)
    );

    topSitesLayer = L.geoJSON({ type: 'FeatureCollection', features: feats }, {
      pointToLayer: (f, ll) => {
        const rank = feats.indexOf(f) + 1;
        return L.marker(ll, { icon: makeCsIcon(rank, f.properties.final_score) });
      },
      onEachFeature: (f, l) => {
        const rank = feats.indexOf(f) + 1;
        l.bindPopup(buildCandidatePopup(f.properties, rank), { maxWidth: 310 });
      }
    });
  });

document.getElementById('sites-toggle').addEventListener('click', () => {
  if (!topSitesLayer) return;
  topSitesVisible = !topSitesVisible;
  topSitesVisible ? topSitesLayer.addTo(map) : map.removeLayer(topSitesLayer);
  setTog('sites-toggle', topSitesVisible);
});

// ── Lakes ──────────────────────────────────────────────────────────
fetch(`${API}/api/lakes`)
  .then(r => r.json())
  .then(geo => {
    lakesLayer = L.geoJSON(geo, {
      style: { color: '#0C447C', fillColor: '#1a5fa5', fillOpacity: 0.45, weight: 0.5 },
      onEachFeature: (f, l) => l.bindTooltip(darkTip(f.properties.name || 'Unnamed Lake'))
    });
  });

document.getElementById('lakes-toggle').addEventListener('click', () => {
  if (!lakesLayer) return;
  lakesVisible = !lakesVisible;
  lakesVisible ? lakesLayer.addTo(map) : map.removeLayer(lakesLayer);
  setTog('lakes-toggle', lakesVisible);
});

// ── Existing turbines ──────────────────────────────────────────────
fetch(`${API}/api/turbines`)
  .then(r => r.json())
  .then(geo => {
    geo.features.forEach(f => {
      const [lon, lat] = f.geometry.coordinates;
      L.circleMarker([lat, lon], {
        radius: 4, color: '#185FA5', fillColor: '#B5D4F4', fillOpacity: 0.9, weight: 1
      })
        .bindPopup(buildTurbinePopup(f.properties), { maxWidth: 280 })
        .addTo(markers);
    });
  });

document.getElementById('turbines-toggle').addEventListener('click', () => {
  turbinesVisible = !turbinesVisible;
  turbinesVisible ? markers.addTo(map) : map.removeLayer(markers);
  setTog('turbines-toggle', turbinesVisible);
});

// ── Data Sources modal ─────────────────────────────────────────────
const srcOverlay = document.getElementById('sources-overlay');

document.getElementById('sources-btn').addEventListener('click', () => {
  srcOverlay.classList.remove('src-hidden');
});

document.getElementById('sources-close').addEventListener('click', () => {
  srcOverlay.classList.add('src-hidden');
});

srcOverlay.addEventListener('click', e => {
  if (e.target === srcOverlay) srcOverlay.classList.add('src-hidden');
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') srcOverlay.classList.add('src-hidden');
});

