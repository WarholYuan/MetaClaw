# Plugin Development

MetaClaw plugins package optional behavior behind an explicit manifest. A
plugin directory should keep runtime code, documentation, and its manifest
together:

```text
my-plugin/
  plugin.json
  my_plugin.py
  README.md
```

## Manifest

`plugin.json` should include:

- `name`: Stable package name.
- `version`: Release version.
- `description`: Short summary for users and marketplace listings.
- `entrypoint`: Python import target in `module.py:ClassName` form.
- `permissions`: Runtime capabilities the plugin needs.
- `config_schema`: Optional JSON Schema for plugin configuration.
- `author` and `homepage`: Optional publisher metadata.

Request only the permissions required for normal operation. Plugin code should
fail with clear errors when required configuration is missing.

## Local Testing

Install or copy the plugin into the local plugin path, enable it in
configuration, and start MetaClaw from a development checkout. Keep examples
small enough that users can inspect permission use quickly.
