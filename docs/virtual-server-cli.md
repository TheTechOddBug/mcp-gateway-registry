# Virtual MCP Server CLI Commands

This document describes CLI commands for managing Virtual MCP Servers. Virtual servers aggregate tools from multiple backend MCP servers into a single unified endpoint.

For the full design and architecture details, see [Virtual MCP Server Design Document](design/virtual-mcp-server.md).

## Prerequisites

- A valid JWT token (saved to a file, e.g., `.token`)
- Registry URL (e.g., `http://localhost` for local development)

## Available Commands

| Command | Description |
|---------|-------------|
| `vs-create` | Create a virtual MCP server from JSON config |
| `vs-list` | List all virtual MCP servers |
| `vs-get` | Get virtual MCP server details |
| `vs-update` | Update a virtual MCP server |
| `vs-delete` | Delete a virtual MCP server |
| `vs-toggle` | Enable or disable a virtual server |
| `vs-rate` | Rate a virtual MCP server (1-5 stars) |
| `vs-rating` | Get rating information |

## Configuration File Format

Virtual servers are created from a JSON configuration file. Here is an example that combines tools from Context7 (documentation search) and CurrentTime (timezone) servers:

```json
{
  "path": "/virtual/combined-tools",
  "server_name": "Combined Context7 and CurrentTime Tools",
  "description": "Virtual server aggregating documentation search tools from Context7 and timezone tools from CurrentTime server",
  "tool_mappings": [
    {
      "tool_name": "resolve-library-id",
      "backend_server_path": "/context7"
    },
    {
      "tool_name": "query-docs",
      "backend_server_path": "/context7"
    },
    {
      "tool_name": "current_time_by_timezone",
      "alias": "get-current-time",
      "backend_server_path": "/currenttime/"
    }
  ],
  "required_scopes": [],
  "tool_scope_overrides": [],
  "tags": [
    "documentation",
    "time",
    "timezone",
    "libraries",
    "combined"
  ],
  "supported_transports": [
    "streamable-http"
  ],
  "is_enabled": true
}
```

See [cli/examples/virtual-server-combined-example.json](../cli/examples/virtual-server-combined-example.json) for the full example.

### Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `path` | Yes | Virtual server path (e.g., `/virtual/dev-tools`) |
| `server_name` | Yes | Display name for the virtual server |
| `description` | No | Description of the virtual server |
| `tool_mappings` | Yes | Array of tool mappings (at least one required) |
| `required_scopes` | No | Server-level scope requirements |
| `tool_scope_overrides` | No | Per-tool scope overrides |
| `tags` | No | Tags for categorization |
| `supported_transports` | No | Supported transports (default: `["streamable-http"]`) |
| `is_enabled` | No | Whether to enable on creation (default: `true`) |

### Tool Mapping Fields

| Field | Required | Description |
|-------|----------|-------------|
| `tool_name` | Yes | Original tool name on backend server |
| `backend_server_path` | Yes | Backend server path (e.g., `/github`) |
| `alias` | No | Renamed tool name in virtual server |
| `backend_version` | No | Pin to specific backend version |
| `description_override` | No | Override tool description |

## Example Usage

### Create a Virtual Server

```bash
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-create --config cli/examples/virtual-server-combined-example.json
```

**Example Output:**

```
Virtual server created: /virtual/combined-tools
{
  "message": "Virtual server created successfully",
  "virtual_server": {
    "path": "/virtual/combined-tools",
    "server_name": "Combined Context7 and CurrentTime Tools",
    "description": "Virtual server aggregating documentation search tools from Context7 and timezone tools from CurrentTime server",
    "is_enabled": false,
    "tool_count": 3
  }
}
```

### List Virtual Servers

```bash
# List all virtual servers
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-list

# List only enabled virtual servers
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-list --enabled-only

# Output as JSON
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-list --json
```

### Get Virtual Server Details

```bash
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-get --path /virtual/combined-tools
```

**Example Output:**

```
Virtual MCP Server: /virtual/combined-tools
------------------------------------------------------------
  Name: Combined Context7 and CurrentTime Tools
  Status: enabled
  Description: Virtual server aggregating documentation search tools from Context7 and timezone tools from CurrentTime server
  Rating: 0.0 stars
  Tags: documentation, time, timezone, libraries, combined
  Transports: streamable-http
  Required Scopes: None

  Tool Mappings (3):
    - resolve-library-id
      Backend: /context7
    - query-docs
      Backend: /context7
    - current_time_by_timezone -> get-current-time
      Backend: /currenttime/

  Created: 2026-02-17T13:35:22.803009Z
  Updated: 2026-02-17T13:35:41.075488Z
  Created By: admin
```

### Enable or Disable a Virtual Server

```bash
# Enable
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-toggle --path /virtual/combined-tools --enabled true

# Disable
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-toggle --path /virtual/combined-tools --enabled false
```

### Update a Virtual Server

```bash
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-update --path /virtual/combined-tools --config updated-config.json
```

### Delete a Virtual Server

```bash
# With confirmation prompt
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-delete --path /virtual/combined-tools

# Skip confirmation
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-delete --path /virtual/combined-tools --force
```

### Rate a Virtual Server

```bash
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-rate --path /virtual/combined-tools --rating 5
```

### Get Virtual Server Rating

```bash
uv run python api/registry_management.py \
    --registry-url http://localhost \
    --token-file .token \
    vs-rating --path /virtual/combined-tools
```

## Web UI Alternative

All virtual server management operations can also be performed through the web UI. The UI provides a guided wizard for creating virtual servers with:

- Server configuration form
- Tool selection from registered backend servers
- Tool aliasing and scope configuration
- Real-time validation

Access the virtual server management UI at `http://localhost/ui/virtual-servers` (or your registry URL).

## Environment Variables

Instead of passing `--registry-url` each time, you can set environment variables:

```bash
export REGISTRY_URL=http://localhost
export TOKEN_FILE=.token

# Then run commands without flags
uv run python api/registry_management.py vs-list
```

## Related Documentation

- [Virtual MCP Server Design Document](design/virtual-mcp-server.md)
- [CLI Reference](cli.md)
- [Server Management](service-management.md)
