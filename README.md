# MCP Servers Collection

This repository contains a collection of [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) servers that can be used with [Amazon Q](https://aws.amazon.com/q/), [Claude Desktop](https://claude.ai/desktop), and other LLMs that support the MCP protocol.

## Available MCP Servers

- [Capital.com MCP Server](src/capital_com_mcp_server/README.md): Exposes the Capital.com trading API as MCP tools for trading operations
  - Search for markets (e.g., EURUSD, AAPL)
  - Get account information and positions
  - Create and manage trading positions
  - Access watchlists

## What is MCP?

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) is an open protocol that standardizes how applications provide context to LLMs. MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities.

## Prerequisites

Make sure you have `uv` installed on your system:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Using with Amazon Q

1. Create an `mcp.json` configuration file in your Amazon Q configuration directory (`~/.aws/amazonq/mcp.json`):
   ```json
   {
     "mcpServers": {
       "capital-com-mcp-server": {
         "command": "uvx",
         "args": ["capital-com-mcp-server"],
         "env": {
           "CAPITAL_BASE_URL": "https://demo-api-capital.backend-capital.com",
           "CAPITAL_API_KEY": "your_api_key_here",
           "CAPITAL_PASSWORD": "your_password_here",
           "CAPITAL_IDENTIFIER": "your_email@example.com",
           "FASTMCP_LOG_LEVEL": "ERROR"
         }
       }
     }
   }
   ```

2. Run Amazon Q with:
   ```bash
   q chat
   ```

3. Amazon Q will automatically start the MCP server and connect to it.

## Using with Claude Desktop

1. In Claude Desktop, go to Settings > Developer section and click on "Edit Config"
   
2. This will open the configuration file. Add the following to the JSON:
   ```json
   {
     "mcpServers": {
       "capital-com-mcp-server": {
         "command": "uvx",
         "args": ["capital-com-mcp-server"],
         "env": {
           "CAPITAL_BASE_URL": "https://demo-api-capital.backend-capital.com",
           "CAPITAL_API_KEY": "your_api_key_here",
           "CAPITAL_PASSWORD": "your_password_here",
           "CAPITAL_IDENTIFIER": "your_email@example.com",
           "FASTMCP_LOG_LEVEL": "ERROR"
         }
       }
     }
   }
   ```

3. Save the file and restart Claude Desktop.

## Example Conversation

```
You: Search for Apple stock on Capital.com

AI: I'll search for Apple stock on Capital.com for you.

[Uses capital-com-mcp-server___search_markets tool]

I found Apple Inc. (AAPL) on Capital.com. Here are the details:
- Epic: AAPL
- Market name: Apple Inc.
- Current bid price: $184.25
- Current ask price: $184.30
- Market status: OPEN

Would you like me to get more information about this stock or perform any trading operations?
```

## Repository Structure

Each MCP server is organized as a separate Python package under the `src/` directory:

```
mcp-servers/
├── README.md
└── src/
    ├── capital_com_mcp_server/
    │   ├── README.md
    │   ├── pyproject.toml
    │   ├── setup.py
    │   ├── capital_com_mcp_server/
    │   │   ├── __init__.py
    │   │   ├── capital_mcp_server.py
    │   │   └── capital_client.py
    │   └── ...
    └── other_mcp_server/
        ├── README.md
        ├── pyproject.toml
        ├── setup.py
        ├── other_mcp_server/
        │   ├── __init__.py
        │   └── ...
        └── ...
```

## Development

To add a new MCP server to this collection:

1. Create a new directory under `src/` with your server name
2. Add the necessary files for your MCP server implementation
3. Include a `pyproject.toml` and `setup.py` in the server directory
4. Add a README.md with usage instructions

## Publishing

Each MCP server can be published to PyPI independently:

```bash
cd src/your_mcp_server
uv build
uv pip publish
```

## GitHub Actions

This repository uses GitHub Actions to automatically build and publish packages to PyPI when a new release is created. The workflow is configured to use a matrix strategy, allowing each package to be built and published independently.

To add a new package to the publishing workflow, update the matrix in `.github/workflows/python-publish.yml`:

```yaml
strategy:
  matrix:
    package: [capital_com_mcp_server, your_new_mcp_server]
```

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/introduction)
- [Amazon Q Documentation](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/what-is.html)
- [Claude Desktop Documentation](https://docs.anthropic.com/claude/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
