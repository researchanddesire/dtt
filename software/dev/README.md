# DTT development

Local settings and helpers for `development-v1` and `development-v2` builds.

- Copy `local.settings.example.json` to the ignored `local.settings.json` here
  and set `server` to the dashboard origin the build should use: `localhost`,
  a loopback address, or a private-LAN address. Without it, development builds
  use `http://127.0.0.1:3000`.
- `development_server.py` validates that origin; `../firmware/pre_build_script.py`
  embeds it as `RAD_SERVER`. Staging and production builds never read it.
- Test: `python -m unittest discover -s software/dev -p 'test_*.py'`.
