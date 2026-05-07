# Marketplace Publishing

The MetaClaw marketplace index is stored in `marketplace/index.json` and
validated by `marketplace/schema.json`.

## Package Requirements

Each published package needs:

- A manifest with name, version, description, entrypoint, permissions, author,
  and homepage where applicable.
- A stable HTTPS manifest URL.
- A SHA-256 checksum for downloadable package archives when available.
- Documentation that explains setup, configuration, and permission use.

## Publishing Flow

1. Validate the package manifest locally.
2. Host the package and manifest at stable HTTPS URLs.
3. Add an entry to `marketplace/index.json`.
4. Update `last_updated` with an ISO 8601 timestamp.
5. Run:

```bash
python -m json.tool marketplace/index.json >/dev/null
python -m json.tool marketplace/schema.json >/dev/null
python -m pytest tests -q
python -m build
```

Index entries should remain small and deterministic. Put extended setup
instructions in package documentation instead of the marketplace index.
