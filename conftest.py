"""Puts every spec's `src` directory on `sys.path`.

Spec suites import their own example package (`specs/<name>/src/<name_with_underscores>/`), which is
only importable once that `src` is on the path. Doing it here, once, rather than per-spec means a
single repo-wide `pytest` run collects `./tests` and every spec suite together.
"""

import sys
from pathlib import Path

for spec_src in sorted((Path(__file__).parent / "specs").glob("*/src")):
  sys.path.insert(0, str(spec_src))
