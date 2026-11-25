import sys
from fastReader.cli import main

if __name__ == "__main__":
    main(['toc'] + sys.argv[1:])
