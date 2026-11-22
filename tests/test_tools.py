from unittest.mock import MagicMock

import pytest

from src.agent.tools import TOOL_DEFINITIONS, dispatch_tool_call
from src.collectors.base import SystemCollector

SAMPLE_INPUTS = {"check_service_status": {"service_name": "nginx"}}


@pytest.mark.parametrize("tool", TOOL_DEFINITIONS, ids=lambda t: t["name"])
def test_every_defined_tool_is_dispatchable(tool):
    collector = MagicMock(spec=SystemCollector)

    dispatch_tool_call(collector, tool["name"], SAMPLE_INPUTS.get(tool["name"], {}))

    assert len(collector.method_calls) == 1


def test_top_processes_forwards_sort_by():
    collector = MagicMock(spec=SystemCollector)

    dispatch_tool_call(collector, "get_top_processes", {"n": 3, "sort_by": "memory"})

    collector.get_top_processes.assert_called_once_with(3, "memory")


def test_tool_names_are_unique():
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert len(names) == len(set(names))
