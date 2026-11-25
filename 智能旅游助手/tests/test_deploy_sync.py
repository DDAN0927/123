"""部署链路完整性：镜像里的知识库，必须真的能走到持久化卷上。

为什么单独立一组测试
--------------------
知识库分档是按**目录**加的（根目录 = 精编、`guides/` = 导览、`spots/` = 清单），
而容器启动时要把内置文档同步进 `$KB_DIR` 这个持久化卷。新增一档时最容易漏的
就是 `start.sh` 里那段同步 —— 生成脚本写了、`COPY knowledge_base` 也带进去了，
但没同步到卷上，于是：

  * 索引照常构建、服务照常启动、`/health` 全绿；
  * 线上 `guided_count` 一直是 0，那一档等于不存在；
  * 没有任何报错，本地跑（KB_DIR 直接指向仓库）也复现不出来。

这组测试只做静态检查：不启动任何进程，纯粹比对「仓库里有哪些档位」和
「部署链路有没有把它们带上」。跑得比一次容器构建快几个数量级。
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "knowledge_base"
START_SH = ROOT / "start.sh"
DOCKERFILE = ROOT / "Dockerfile"


def _kb_subdirs() -> list[str]:
    """知识库里实际存在的档位子目录（不写死名单：加一档就自动纳入检查）。"""
    if not KB.is_dir():
        return []
    return sorted(d.name for d in KB.iterdir() if d.is_dir())


def test_knowledge_base_has_tiers():
    """三档目录都应该在仓库里，否则下面的检查会「空跑通过」。"""
    subs = _kb_subdirs()
    assert "guides" in subs, f"缺少导览档目录 knowledge_base/guides/，实际：{subs}"
    assert "spots" in subs, f"缺少清单档目录 knowledge_base/spots/，实际：{subs}"


@pytest.mark.parametrize("sub", _kb_subdirs())
def test_start_sh_syncs_every_tier(sub):
    """每个档位子目录都必须在 start.sh 里被同步进 $KB_DIR。

    判据是 `sync_tier <目录名>` 这一行：故意用显式调用而不是「遍历所有子目录」，
    这样新增档位时忘了加一行会被这里抓住，而不是被一个聪明的通配符默默兜住。
    """
    script = START_SH.read_text(encoding="utf-8")
    assert "sync_tier()" in script, "start.sh 里没有 sync_tier 函数，同步逻辑被改掉了"
    assert f"sync_tier {sub}" in script, (
        f"start.sh 没有把 knowledge_base/{sub}/ 同步到 $KB_DIR —— 镜像里躺着、线上用不到，且不会报任何错"
    )


def _sh_code_lines(path: Path) -> list[str]:
    """去掉注释与空行后的 shell 代码行。

    必须去注释：start.sh 里那段说明恰好写着「为什么不用 cp -n」「为什么不用 cp -u」，
    直接在全文里找子串会把解释文字当成违规代码。
    """
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(stripped)
    return out


def test_start_sh_sync_uses_content_compare():
    """同步必须按内容比较，不能用 cp -n / cp -u。

    `cp -n` 会让镜像里的更新永远进不了已有卷；`cp -u` 比 mtime，而镜像层与卷的
    时钟来源不同，判不准。两个都曾经导致「本地正常、线上一直答旧内容」。
    """
    code = _sh_code_lines(START_SH)
    assert any("cmp -s" in ln for ln in code), "同步逻辑不再按内容比较（cmp -s），可能退回 cp -n 的老坑"
    assert not any("cp -n" in ln for ln in code), "start.sh 又用回 cp -n 了：已存在的文件永远不会被更新"
    assert not any("cp -u" in ln for ln in code), "start.sh 用 cp -u 比 mtime，镜像层与卷时钟不同源，判不准"


def test_dockerfile_copies_knowledge_base_tree():
    """Dockerfile 必须整目录 COPY，子目录才会跟着进镜像。"""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY knowledge_base ./knowledge_base" in text, (
        "Dockerfile 没有整目录 COPY knowledge_base，guides/ 与 spots/ 会缺失"
    )


def test_start_sh_has_springboot_watchdog():
    """双进程模式下必须有看门狗：SpringBoot 起不来要退回单进程。

    否则 Java 侧一挂，整站黑屏（连 AI 对话都打不开），而平台只给一句
    「starting studio failed」、不给日志，排查成本极高。退回单进程至少保证
    「AI 可用」，用户不会看到一片白。
    """
    code = _sh_code_lines(START_SH)
    assert any("退回单进程" in ln for ln in code), "start.sh 缺少 SpringBoot 起不来时的单进程回退"
    assert any("app_ready" in ln for ln in code), "start.sh 没有探测 SpringBoot 端口就绪"


def test_image_ships_prebuilt_index():
    """镜像必须自带预构建索引，且 `start.sh` 要把它装进 `$DATA_DIR`。

    这两件事少一件，冷启动就得在 lifespan 里同步重建 1042 块 —— 2 核容器上
    3~5 分钟，正好压在平台自己的启动超时上，表现成
    「starting studio failed, please check the log.」（平台不给日志，看起来像代码坏了）。
    """
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "build_index()" in dockerfile, (
        "Dockerfile 没有在构建期预构建索引，冷启动会重建 1042 块并可能撞上平台启动超时"
    )
    # 预构建那一层必须排在 app/ 与 knowledge_base/ 之后，否则 RUN 时源码还不存在
    idx_run = dockerfile.index("build_index()")
    assert dockerfile.index("COPY app ./app") < idx_run, "预构建索引排在 COPY app 之前，跑不起来"
    assert dockerfile.index("COPY knowledge_base ./knowledge_base") < idx_run, (
        "预构建索引排在 COPY knowledge_base 之前，会建出一个空索引"
    )

    code = _sh_code_lines(START_SH)
    assert any("data/index/faiss.index" in ln for ln in code), (
        "start.sh 没有把镜像里的预构建索引装进 $DATA_DIR —— 镜像里那份索引成了死重量"
    )
