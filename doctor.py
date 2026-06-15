from __future__ import annotations

import sys

from main import main


sys.argv = [sys.argv[0], "doctor", *sys.argv[1:]]
raise SystemExit(main())
