def connection_string(cfg):
    db = cfg["database"]
    return f"{db['url']}?pool={db['pool']}"
