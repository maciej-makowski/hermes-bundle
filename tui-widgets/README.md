# TUI widgets

`<name>.mjs` files, each default-exporting `register(sdk)`. Hermes reads them from
`$HERMES_HOME/tui-widgets/`; there is no install command, so `scripts/install.sh` copies
them and `scripts/uninstall.sh` removes them.
