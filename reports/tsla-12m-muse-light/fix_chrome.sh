#!/bin/bash
which choreo_get_chrome && choreo_get_chrome || python -m choreographer.cli.get_chrome || echo "NO_GETTER"
ls ~/.local/share/choreographer/deps/ 2>/dev/null
google-chrome --version 2>/dev/null; chromium --version 2>/dev/null; echo done
