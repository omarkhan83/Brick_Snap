# Vendored libraries

The viewer makes no request to any other web site, so the libraries it needs are copied here.

## three.js

- Version: **0.186.1** (released 2026-09-24)
- Source: the npm registry tarball <https://registry.npmjs.org/three/-/three-0.186.1.tgz>
  (sha1 `6d50f70c2c437f844179bbb56d6f5b774e1ca38a`, as listed by the registry)
- Licence: MIT, see `LICENSE` in this folder (copied from the same tarball).

Files, copied unchanged from the tarball:

| File here | Path in the tarball |
|---|---|
| `three.module.js` | `package/build/three.module.js` |
| `three.core.js` | `package/build/three.core.js` (imported by `three.module.js`) |
| `OrbitControls.js` | `package/examples/jsm/controls/OrbitControls.js` |
| `LICENSE` | `package/LICENSE` |

`OrbitControls.js` imports from the bare name `three`; `viewer/index.html` maps that name to
`./vendor/three.module.js` with an import map.

To upgrade, download the new tarball, replace all three JavaScript files from the same release,
and update this file.
