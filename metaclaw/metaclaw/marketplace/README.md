# MetaClaw Marketplace

The marketplace index lists distributable MetaClaw skills, tools, and plugins.
`index.json` is intentionally empty until packages are reviewed and published.

## Publishing

1. Create a package manifest (`plugin.json`, skill manifest, or tool manifest).
2. Validate the manifest with the matching schema module.
3. Host the package and manifest at stable HTTPS URLs.
4. Add an entry to `marketplace/index.json` with the package type, name,
   version, description, `manifest_url`, and optional SHA-256 checksum.
5. Run:

```bash
python -m json.tool marketplace/index.json >/dev/null
python -m json.tool marketplace/schema.json >/dev/null
```

Marketplace entries should request the minimum permissions needed for normal
operation and should document any external services they contact.
