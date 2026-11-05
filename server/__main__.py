"""python -m server            -> run HTTPS server on 8787
python -m server bootstrap  -> create schema + root tree, print root token"""
import os
import sys

if len(sys.argv) > 1 and sys.argv[1] == "bootstrap":
    from server.bootstrap import main
    main()
else:
    import uvicorn
    from server.tls import ensure_cert
    cert, key = ensure_cert()
    uvicorn.run("server.app:app", host=os.environ.get("PLANNER_HOST", "0.0.0.0"), port=int(os.environ.get("PLANNER_PORT", "8787")),
                ssl_certfile=str(cert), ssl_keyfile=str(key))
