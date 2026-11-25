import sys
from fastReader.cli import main

if __name__ == "__main__":
    main(['search'] + sys.argv[1:])
