"""User-run report interpretation; never opens assets or configuration files."""

from mtah.diagnostics import main

if __name__ == "__main__":
    raise SystemExit(main())
