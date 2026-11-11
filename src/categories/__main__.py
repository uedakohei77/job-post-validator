import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.categories.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
