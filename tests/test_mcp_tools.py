import json

import pytest

from supplyguard.mcp_server import disaster_statistics, lookup_disasters


def test_mcp_rejects_invalid_state_code():
    with pytest.raises(ValueError):
        lookup_disasters("California")
    with pytest.raises(ValueError):
        disaster_statistics("California", 2025)
    with pytest.raises(ValueError):
        disaster_statistics("CA", 1900)


def test_mcp_computes_from_full_csv():
    result = json.loads(disaster_statistics("CA", 2025))
    assert result["total"] > 0
    assert result["source"].startswith("OpenFEMA")
