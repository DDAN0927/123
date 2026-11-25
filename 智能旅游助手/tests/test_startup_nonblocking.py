"""启动不能被索引重建拖住。

背景：索引重建是 CPU 密集的（1042 块，2 核容器 3~5 分钟），而 uvicorn 要等
lifespan 跑完才 bind 端口。同步重建时端口迟迟不开，部署平台会判定
「starting studio failed」——平台超时比我们自己的 420 秒更短，且不给日志，
排查起来像是代码坏了。魔搭 dd 站就是这样连续两次 DeployFailed 的。

这组测试只验证一件事：`_ensure_index()` 发现索引过期时**立刻返回**，
把重建交给后台线程。
"""

import threading
import time

from app import main
from app.rag import indexer, retriever


def test_ensure_index_returns_immediately(monkeypatch):
    started = []

    def slow_build():
        started.append(threading.current_thread().name)
        time.sleep(1.0)  # 模拟 3~5 分钟的重建
        return {"documents": 1, "chunks": 1, "dimension": 512}

    monkeypatch.setattr(retriever, "index_ready", lambda: True)
    monkeypatch.setattr(indexer, "index_stale", lambda: True)
    monkeypatch.setattr(indexer, "load_documents", lambda: [("测试.md", "内容")])
    monkeypatch.setattr(indexer, "build_index", slow_build)
    monkeypatch.setattr(retriever, "reset", lambda: None)
    monkeypatch.setattr(retriever, "warmup", lambda: None)

    t0 = time.time()
    main._ensure_index()
    elapsed = time.time() - t0

    assert elapsed < 0.5, f"_ensure_index 阻塞了 {elapsed:.2f}s，端口会迟迟不开"

    for _ in range(60):
        if started:
            break
        time.sleep(0.05)
    assert started, "后台线程没有开始重建索引"
    assert started[0] != threading.current_thread().name, "重建跑在了调用方线程里"


def test_ensure_index_noop_when_fresh(monkeypatch):
    """索引与知识库一致时不该启动任何重建线程。"""
    monkeypatch.setattr(retriever, "index_ready", lambda: True)
    monkeypatch.setattr(indexer, "index_stale", lambda: False)
    monkeypatch.setattr(indexer, "build_index", lambda: (_ for _ in ()).throw(AssertionError("不该重建")))

    before = threading.active_count()
    main._ensure_index()
    assert threading.active_count() == before
