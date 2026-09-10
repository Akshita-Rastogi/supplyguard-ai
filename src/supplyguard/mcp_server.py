import csv
import json
import os
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

try:
    from mcp.server import MCPServer
except ImportError:  # pragma: no cover - compatibility with MCP 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

    MCP_V2 = False
else:
    MCP_V2 = True

DATA_PATH = Path(os.getenv("DATA_PATH", "data/raw/public/fema_disaster_declarations_full.csv"))
mcp = MCPServer("SupplyGuard Risk Tools")


@lru_cache(maxsize=1)
def rows():
    """Load the immutable local CSV once per MCP process to avoid repeated disk scans."""
    with DATA_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return tuple(csv.DictReader(handle))


@mcp.tool()
def lookup_disasters(state: str, incident_type: str = "", limit: int = 10) -> str:
    """Return FEMA declarations for an exact US state code and optional incident type."""
    state = state.strip().upper()
    if len(state) != 2 or not state.isalpha():
        raise ValueError("state must be a two-letter code")
    safe_limit = max(1, min(limit, 50))
    matches = [row for row in rows() if row["state"] == state and
               (not incident_type or row["incidentType"].casefold() == incident_type.casefold())]
    matches.sort(key=lambda row: row["declarationDate"], reverse=True)
    return json.dumps({"source": "OpenFEMA DisasterDeclarationsSummaries v2",
                       "count": len(matches), "results": matches[:safe_limit]})


@mcp.tool()
def disaster_statistics(state: str = "", year: int = 0) -> str:
    """Compute incident-type counts from the local FEMA CSV snapshot."""
    state = state.strip().upper()
    if state and (len(state) != 2 or not state.isalpha()):
        raise ValueError("state must be empty or a two-letter code")
    if year and not 1953 <= year <= datetime.now(UTC).year:
        raise ValueError("year must be empty or within the FEMA dataset range")
    selected_rows = [row for row in rows() if (not state or row["state"] == state.upper()) and
                     (not year or row["fyDeclared"] == str(year))]
    # The source repeats a disaster for each designated area. Tool-level
    # statistics report unique declarations and expose the raw row count.
    selected = list({row["disasterNumber"]: row for row in selected_rows}.values())
    return json.dumps({"source": "OpenFEMA DisasterDeclarationsSummaries v2",
                       "filters": {"state": state or None, "year": year or None},
                       "total": len(selected),
                       "designated_area_rows": len(selected_rows),
                       "by_incident_type": Counter(row["incidentType"] for row in selected).most_common()})


if __name__ == "__main__":
    # Streamable HTTP keeps the tool in a separate, independently failing process.
    options = {"host": os.getenv("MCP_HOST", "127.0.0.1"),
               "port": int(os.getenv("MCP_PORT", "8001"))}
    if MCP_V2:
        mcp.run(transport="streamable-http", **options)
    else:  # MCP 1.x reads host/port from the FastMCP settings object.
        mcp.settings.host = options["host"]
        mcp.settings.port = options["port"]
        mcp.run(transport="streamable-http")
