import sys
from planning_system.fastreader.cli import main

if __name__ == "__main__":
    main(['load'] + sys.argv[1:])
