# hermes-bundle

Maciek's Hermes extensions in one place: plugins, skills, desktop plugins, TUI widgets,
skins and pets, installed from a single manifest.

Design record: `maciej-makowski/hermes-designs` (PROPOSED, hermes-plugin-bundle).

## Install

```bash
git clone https://github.com/maciej-makowski/hermes-bundle.git
cd hermes-bundle
./scripts/install.sh --dry-run   # show the exact commands
./scripts/install.sh --yes       # install everything, non-interactively
```

The script is the all-in-one path: it installs the plugin, the catalog component, adds
the tap and installs every skill. Run it straight from curl if you do not want a checkout:

```bash
curl -fsSL https://raw.githubusercontent.com/maciej-makowski/hermes-bundle/main/scripts/install.sh | bash -s -- --yes
```

Add `--allow-caution` to accept a caution scan verdict for the skills that carry it; the
flag prints each acceptance, and a `dangerous` verdict is still refused.

A pack installs the plugin half natively, pinned to one commit:

```bash
hermes plugins pack show ./hermes-pack.yaml
hermes plugins pack install ./hermes-pack.yaml
```

A pack never installs the skills it lists, so skills always come from the tap.

One component at a time:

```bash
./scripts/install.sh --component design-doc-edit --yes
```

Native commands work too. A plugin installs from its subdirectory:

```bash
hermes plugins install maciej-makowski/hermes-bundle/plugins/design-doc-edit --enable
```

Do not run `hermes plugins install maciej-makowski/hermes-bundle` on its own: it installs
the whole repo as one plugin, which this repo is not.

## Update

```bash
./scripts/update.sh
```

Update is per name. `hermes plugins update` with no name, Desktop update-all and
auto-update skip subdirectory installs, so the script loops over the manifest instead.

## Components

| Component | Type | Route |
|---|---|---|
| design-doc-edit | plugin | `hermes plugins install .../plugins/design-doc-edit` |
| holographic | catalog plugin | `hermes plugins install holographic` |
| unslop, hermes-desktop-plugins, hermes-themes, hermes-session-storage, nvme-drive-qualification, jump-box-ops, hermes-container-extension, hermes-container-restart-mechanism, strava-stack | skills | `hermes skills tap add maciej-makowski/hermes-bundle`, then install each |

Desktop plugins, TUI widgets, skins and pets have no native install route; the script
copies them into `$HERMES_HOME` and `doctor.sh` reports divergence. A desktop-only plugin
needs the Desktop "Install from Git" dialog, pinned to a reviewed commit.

## Layout

```
bundle.yaml            component manifest read by scripts/
plugins/<name>/        Python plugins, one directory each
skills/<name>/         tap root, one SKILL.md per skill
desktop-plugins/       desktop-only plugins (dialog install)
tui-widgets/           *.mjs widgets
skins/                 *.yaml skins
pets/                  <slug>/ pet directories
scripts/               install, update, doctor, uninstall, scrub-check
```

There is no `plugin.yaml` at the repo root on purpose. See the design record.

## Licence

MIT for the first-party code in this repository. Third-party components keep their own
licences; the README of each component says which.
