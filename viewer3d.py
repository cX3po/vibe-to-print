"""
viewer3d.py — Self-contained Three.js STL viewer for Streamlit.

Usage:
    import streamlit.components.v1 as components
    import viewer3d as v3d
    components.html(v3d.stl_viewer_html(stl_bytes), height=380, scrolling=False)
"""

import base64


def stl_viewer_html(stl_bytes: bytes, height: int = 380, bg: str = "#0d1b2a") -> str:
    """Return a self-contained HTML page that renders an STL in Three.js."""
    b64 = base64.b64encode(stl_bytes).decode()
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:{bg};overflow:hidden;width:100%;height:{height}px;font-family:sans-serif}}
#hint{{position:fixed;bottom:7px;left:0;right:0;text-align:center;
      color:#2d4a60;font-size:11px;pointer-events:none;user-select:none}}
#info{{position:fixed;top:7px;left:10px;color:#52b788;font-size:12px;
      pointer-events:none;user-select:none}}
#err{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
     color:#e94560;font-size:14px;text-align:center;display:none;
     background:rgba(13,27,42,0.9);padding:16px;border-radius:8px}}
</style></head>
<body>
<div id="info">Loading…</div>
<div id="hint">🖱 Drag to rotate &nbsp;·&nbsp; Scroll to zoom &nbsp;·&nbsp; Right-drag to pan</div>
<div id="err"></div>
<script type="module">
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.module.js';
import {{ STLLoader }}     from 'https://cdn.jsdelivr.net/npm/three@0.160.1/examples/jsm/loaders/STLLoader.js';
import {{ OrbitControls }} from 'https://cdn.jsdelivr.net/npm/three@0.160.1/examples/jsm/controls/OrbitControls.js';

try {{
  const H = {height};
  const renderer = new THREE.WebGLRenderer({{antialias: true}});
  renderer.setPixelRatio(devicePixelRatio);
  renderer.setSize(window.innerWidth, H);
  renderer.shadowMap.enabled = true;
  document.body.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("{bg}");

  // Lighting — key, fill, rim
  const key  = new THREE.DirectionalLight(0xffffff, 1.4);
  key.position.set(1, 2, 1.5);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0x4a8fc0, 0.5);
  fill.position.set(-1, -0.5, -1);
  scene.add(fill);
  const rim  = new THREE.DirectionalLight(0xe0f0ff, 0.3);
  rim.position.set(0, -1, 0);
  scene.add(rim);
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));

  const camera   = new THREE.PerspectiveCamera(42, window.innerWidth / H, 0.01, 1e6);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping  = true;
  controls.dampingFactor  = 0.06;
  controls.minDistance    = 0.1;

  // Decode base64 STL
  const raw = atob("{b64}");
  const buf = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);

  const geo = new STLLoader().parse(buf.buffer);
  geo.computeVertexNormals();
  geo.computeBoundingBox();

  const box    = geo.boundingBox;
  const size   = new THREE.Vector3(); box.getSize(size);
  const center = new THREE.Vector3(); box.getCenter(center);
  const maxDim = Math.max(size.x, size.y, size.z);

  const mat  = new THREE.MeshPhongMaterial({{
    color: 0x3a78c9, specular: 0x1a3a6a, shininess: 90,
    side: THREE.DoubleSide
  }});
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.sub(center);

  // Grid helper at base of model
  const grid = new THREE.GridHelper(maxDim * 2, 12, 0x1d3557, 0x1d3557);
  grid.position.y = -size.z / 2;

  scene.add(mesh, grid);

  camera.position.set(maxDim * 1.6, maxDim * 0.9, maxDim * 1.6);
  camera.lookAt(0, 0, 0);
  controls.update();

  // Info line
  const tris = geo.index ? geo.index.count / 3 : geo.attributes.position.count / 3;
  document.getElementById('info').textContent =
    `${{size.x.toFixed(1)}} × ${{size.y.toFixed(1)}} × ${{size.z.toFixed(1)}} mm  ·  ${{Math.round(tris).toLocaleString()}} triangles`;

  window.addEventListener('resize', () => {{
    const nW = window.innerWidth;
    camera.aspect = nW / H;
    camera.updateProjectionMatrix();
    renderer.setSize(nW, H);
  }});

  (function animate() {{
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }})();

}} catch (e) {{
  const d = document.getElementById('err');
  d.style.display = 'block';
  d.innerHTML = '⚠️ 3D viewer error<br><small>' + e.message + '</small>';
  console.error(e);
}}
</script></body></html>"""
