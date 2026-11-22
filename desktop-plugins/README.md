# Desktop plugins

Desktop-only plugins live here as `<name>/plugin.js` plus a metadata-only `plugin.yaml`.
They install through the Desktop "Install from Git" dialog, pinned to a reviewed commit;
there is no CLI install route for a desktop-only plugin.

A plugin that also has a Python half ships `desktop/plugin.js` inside its own directory
under `plugins/`, and one CLI install materialises both halves.
