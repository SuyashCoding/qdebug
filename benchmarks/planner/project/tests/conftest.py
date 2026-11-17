import pytest

from planner.parser import parse_plan

SAMPLE = """
# website relaunch
design: 3d @ana !high #ux
copy: 2d @cy #content
build: 1w after design @ben #core #backend
review: 2d after build, copy @ana !urgent #ux
launch: milestone after review
"""


@pytest.fixture
def plan():
    return parse_plan(SAMPLE, "relaunch")
