# util/common: follow-ups

## Subprocess helper: wrong kwarg for stderr (`TODO`)

In `util/common/__init__.py`, `_operation()` calls `_docker()` with
`on_stderr=lambda line: ...`, but `_execute()` only looks for
`on_stderr_line` (see `kwargs.get('on_stderr_line', None)`). The
`on_stderr` argument is therefore never used.

Additionally, `subprocess.Popen` is started with `stderr=subprocess.STDOUT`,
so child stderr is merged into stdout; the `on_stderr_line` branch in
`_execute` would only run if stderr were a separate pipe. Worth cleaning up
when someone touches this (either wire `on_stderr` → `on_stderr_line`, drop
the dead stderr branch, or split pipes if stderr streaming is actually
needed).

---

## Docker: `docker: 'compose' is not a docker command`

The helpers invoke **`docker compose`** (Compose as a Docker CLI plugin). If
only the legacy **`docker-compose`** binary is installed, that error appears.

**To fix without changing Python:** install the Compose V2 **plugin** so
`docker compose` exists.

`docker-compose-plugin` is **not** in default Debian/Ubuntu repos—you get it
from **Docker’s APT repo** (same place as `docker-ce`). If `apt` says “Unable
to locate package”, add that repo first:

- Follow [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
  or [on Debian](https://docs.docker.com/engine/install/debian/) (pick your
  distro; steps include adding `download.docker.com` and then installing
  packages).
- Then: `sudo apt-get update && sudo apt-get install docker-compose-plugin`
- Verify: `docker compose version`

Fedora (with Docker’s dnf repo): `sudo dnf install docker-compose-plugin`

**Other options:** [manual plugin install](https://docs.docker.com/compose/install/linux/#install-the-plugin-manually)
from GitHub releases; or keep standalone `docker-compose` and add a small
Python fallback in `util/common/__init__.py` (try `docker compose` first, then
`docker-compose`).
