from __future__ import annotations

import pytest


@pytest.mark.qlib
def test_qlib_optional_version() -> None:
    qlib = pytest.importorskip("qlib")
    assert qlib.__version__ == "0.9.7"
