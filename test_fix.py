#!/usr/bin/env python3
import sys
import signal
import os

# Add the server directory to path
sys.path.insert(0, '/Users/syedhumair/Documents/projects/mcp-servers/src/capital_com_mcp_server')

def timeout_handler(signum, frame):
    print("SUCCESS: Server started without errors")
    sys.exit(0)

try:
    import fastmcp
    mcp = fastmcp.FastMCP('test-server')

    @mcp.tool
    def test() -> str: 
        return 'ok'

    print("Testing streamable-http without host parameter...")
    
    # Set timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(3)
    
    # This should not error out immediately
    mcp.run(transport='streamable-http', port=8089)
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    sys.exit(1)