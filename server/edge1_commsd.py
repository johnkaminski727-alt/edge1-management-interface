#!/usr/bin/env python3
"""Run the unified WW.CX Edge1 IRC, NNTP and read-only control services."""
from __future__ import annotations
import argparse,signal,threading
from pathlib import Path
from edge1_comms.config import load_config
from edge1_comms.control import ControlServer
from edge1_comms.irc import IrcServer
from edge1_comms.nntp import NntpServer
from edge1_comms.storage import CommsStore
REPO_ROOT=Path(__file__).resolve().parents[1]; WEB_ROOT=REPO_ROOT/'src'/'web'/'comms-relay'
def parser():
    item=argparse.ArgumentParser(description=__doc__);item.add_argument('--config');return item
def main()->int:
    args=parser().parse_args();cfg=load_config(args.config);store=CommsStore(cfg.database_path,password_iterations=cfg.security.password_iterations,min_password_length=cfg.security.min_password_length,default_news_days=cfg.retention.default_news_days,irc_history_days=cfg.retention.irc_history_days,audit_days=cfg.retention.audit_days);store.prune_retention();servers=[]
    try:
        if cfg.irc.enabled:servers.append(IrcServer((cfg.irc.host,cfg.irc.port),cfg,store))
        if cfg.nntp.enabled:servers.append(NntpServer((cfg.nntp.host,cfg.nntp.port),cfg,store))
        if cfg.control.enabled:
            irc=next((s for s in servers if isinstance(s,IrcServer)),None);servers.append(ControlServer((cfg.control.host,cfg.control.port),cfg,store,web_root=WEB_ROOT,irc_summary=irc.hub.summary if irc is not None else None))
    except Exception:
        for server in servers:
            try:server.server_close()
            except Exception:pass
        raise
    if not servers:raise SystemExit('no listeners are enabled')
    stop=threading.Event()
    def request_stop(signum:int,frame:object)->None:stop.set()
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    threads=[threading.Thread(target=s.serve_forever,kwargs={'poll_interval':0.2},daemon=True) for s in servers]
    for t in threads:t.start()
    def maintenance()->None:
        while not stop.wait(cfg.retention.maintenance_interval_seconds):
            removed=store.prune_retention();store.checkpoint()
            if any(removed.values()):store.audit(None,'control','retention.prune',cfg.server_name,'ok',removed)
    mt=threading.Thread(target=maintenance,daemon=True,name='comms-retention');mt.start();store.audit(None,'control','service.start',cfg.server_name,'ok',{'listeners':len(servers)});stop.wait()
    for s in servers:s.shutdown()
    for s in servers:s.server_close()
    for t in threads:t.join(timeout=5)
    mt.join(timeout=2);store.checkpoint();store.audit(None,'control','service.stop',cfg.server_name,'ok',{});return 0
if __name__=='__main__':raise SystemExit(main())
