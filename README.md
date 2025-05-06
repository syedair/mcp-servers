# MCP Servers Collection

This repository contains a collection of [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) servers that can be used with [Amazon Q](https://aws.amazon.com/q/) and other LLMs that support the MCP protocol.

## Available MCP Servers

- [Capital.com MCP Server](src/capital_com_mcp_server/README.md): Exposes the Capital.com trading API as MCP tools

## What is MCP?

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) is an open protocol that standardizes how applications provide context to LLMs. MCP enables communication between the system and locally running MCP servers that provide additional tools and resources to extend LLM capabilities.

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
    │   ├── __init__.py
    │   └── ...
    └── other_mcp_server/
        ├── README.md
        ├── pyproject.toml
        ├── setup.py
        ├── __init__.py
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
