import json, glob, sys
for f in sorted(glob.glob(f"{__file__.rsplit('/',1)[0]}/raw/{sys.argv[1]}*.json")):
    r = json.load(open(f)); print("==", f.split("/")[-1], repr(r["final"][:int(sys.argv[2]) if len(sys.argv) > 2 else 220]))
