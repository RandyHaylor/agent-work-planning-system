import sys
from fastReader.cli import main

if __name__ == "__main__":
    main(['load'] + sys.argv[1:])
