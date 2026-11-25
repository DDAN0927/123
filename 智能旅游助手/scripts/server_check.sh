#!/usr/bin/env bash
# SpringBoot 主后端的编译 + 单元/集成测试
#
#   bash scripts/server_check.sh
#
# 退出码：0 通过 / 1 失败 / 2 跳过（本机没装 JDK 或 Maven）
#
# 为什么要单独一个脚本：Java 侧和 Python 侧的依赖完全不同（JDK 17 + Maven 3.9），
# 很多人只会装其中一套。装在 .tools/ 里的可以直接用；没装就**跳过而不是失败**，
# 免得「没装 JDK」被当成「代码有 bug」。

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

# ---------- 解析 JDK ----------
if [ -z "${JAVA_HOME:-}" ]; then
  for cand in ".tools/jdk/jdk-17.0.2" ".tools/jdk/jdk-17"; do
    if [ -x "$cand/bin/javac" ] || [ -x "$cand/bin/javac.exe" ]; then
      JAVA_HOME="$(cd "$cand" && pwd)"
      break
    fi
  done
fi
if [ -z "${JAVA_HOME:-}" ] || [ ! -d "$JAVA_HOME" ]; then
  echo "未找到 JDK 17（可放到 .tools/jdk/ 或设置 JAVA_HOME），跳过 Java 侧检查"
  exit 2
fi
export JAVA_HOME

# ---------- 解析 Maven ----------
MVN=""
for cand in ".tools/maven/apache-maven-3.9.16/bin/mvn" ".tools/maven/bin/mvn"; do
  [ -x "$cand" ] && MVN="$PWD/$cand" && break
done
if [ -z "$MVN" ]; then
  MVN="$(command -v mvn || true)"
fi
if [ -z "$MVN" ]; then
  echo "未找到 Maven（可放到 .tools/maven/ 或加入 PATH），跳过 Java 侧检查"
  exit 2
fi

# 路径都转成绝对路径：下面会 cd 进 server/，相对路径会失效
SETTINGS=""
[ -f ".tools/maven/settings.xml" ] && SETTINGS="-s $PWD/.tools/maven/settings.xml"

echo "JAVA_HOME: $JAVA_HOME"
echo "mvn      : $MVN"
echo

# -o 离线：测试不该在回归时去 Maven 中央仓库拉包（网络抖一下就是假失败）。
# 依赖没预热过时 -o 会直接失败，此时提示一句怎么预热，而不是让人对着
# "Cannot access central in offline mode" 发愣。
cd server || exit 1
if ! "$MVN" -o $SETTINGS -q test > /tmp/travel-server-test.log 2>&1; then
  if grep -q "offline mode" /tmp/travel-server-test.log; then
    echo "本地仓库缺依赖，请先联网执行一次：cd server && mvn $SETTINGS dependency:go-offline"
    exit 1
  fi
  tail -n 60 /tmp/travel-server-test.log
  exit 1
fi

# surefire 的汇总在 target/surefire-reports/*.txt 里；没生成说明测试根本没跑
TOTAL=0
FAIL=0
for f in target/surefire-reports/*.txt; do
  [ -e "$f" ] || continue
  line="$(grep -h "^Tests run:" "$f" | tail -n 1)"
  [ -z "$line" ] && continue
  t="$(printf '%s' "$line" | sed -n 's/.*Tests run: \([0-9]*\).*/\1/p')"
  fa="$(printf '%s' "$line" | sed -n 's/.*Failures: \([0-9]*\).*/\1/p')"
  er="$(printf '%s' "$line" | sed -n 's/.*Errors: \([0-9]*\).*/\1/p')"
  TOTAL=$((TOTAL + ${t:-0}))
  FAIL=$((FAIL + ${fa:-0} + ${er:-0}))
done

if [ "$TOTAL" -eq 0 ]; then
  echo "没有跑到任何测试用例（surefire 报告为空），视为失败"
  exit 1
fi
if [ "$FAIL" -gt 0 ]; then
  echo "Java 测试：$((TOTAL - FAIL))/$TOTAL 通过，$FAIL 个失败"
  tail -n 40 /tmp/travel-server-test.log
  exit 1
fi
echo "Java 测试：$TOTAL/$TOTAL 通过"
