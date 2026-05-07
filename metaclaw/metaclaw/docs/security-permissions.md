# Security Permissions

MetaClaw ecosystem packages declare permissions before they are installed or
published. Permissions are a review contract: they document what the package may
do and help users decide whether to trust it.

## Skill Permissions

Skill manifests use a string list such as:

- `filesystem`: Reads or writes local files.
- `shell`: Runs local shell commands.
- `browser`: Drives a browser session.
- `web_search`: Searches or fetches web content.
- `opencli`: Uses OpenCLI adapters.

## Tool Permissions

Tool manifests use boolean flags:

```json
{
  "filesystem": false,
  "shell": false,
  "browser": false,
  "web_search": true,
  "opencli": false
}
```

## Review Guidance

Packages should request the smallest permission set possible. Shell and
filesystem access require extra scrutiny because they can change local state.
Network-enabled packages should document the services they contact and what
data is sent.
