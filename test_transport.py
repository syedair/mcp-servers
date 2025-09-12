#!/usr/bin/env python3

import sys
sys.path.insert(0, '/Users/syedhumair/Documents/projects/mcp-servers/src/capital_com_mcp_server')

try:
    import fastmcp
    print(f"FastMCP version: {fastmcp.__version__}")
    
    # Create a simple test server
    mcp = fastmcp.FastMCP('test-server')
    
    @mcp.tool
    def test_tool() -> str:
        return "test"
    
    # Try to inspect the run method signature
    import inspect
    sig = inspect.signature(mcp.run)
    print(f"run() method signature: {sig}")
    
    # Test different transport names
    transports_to_test = ['streamable-http', 'streamable_http', 'http']
    
    for transport in transports_to_test:
        try:
            print(f"Testing transport: {transport}")
            # This should fail quickly if transport name is invalid
            mcp.run(transport=transport, host='0.0.0.0', port=8088)
        except Exception as e:
            print(f"  Error with {transport}: {type(e).__name__}: {e}")
            if "Invalid transport" in str(e) or "transport" in str(e).lower():
                print(f"  -> {transport} is not a valid transport")
            else:
                print(f"  -> {transport} might be valid, error was: {e}")
                break  # Stop on first non-transport error
        
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Unexpected error: {type(e).__name__}: {e}")