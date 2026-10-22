# -*- coding: utf-8 -*-
"""
腾讯云 SCF（Serverless 云函数）入口 · 武汉菜篮子全量抓取

为什么要有这个文件：
    发改委接口是裸 IP（58.48.136.167:7600），GitHub Actions 的机器在境外，
    连不上，所以云端只能跑 daily（只抓当天）。SCF 是国内 IP，能跑 full，
    可以把真实 52 周历史补齐。

执行流程：
    1. 从仓库拉最新 data.json 放到 /tmp，作为 full 的基准
       （full_fetch 里的 restore_fgj_items 依赖它，手里没基准会丢历史）
    2. 切到 /tmp 执行 full_fetch（fetch_data.py 用相对路径写 data.json）
    3. 校验产出，不合格就中止，绝不推脏数据
    4. 通过 GitHub Contents API 覆盖提交

环境变量（函数配置 → 环境变量）：
    GH_TOKEN   必填，fine-grained PAT，只需本仓库 Contents: Read and write
    GH_REPO    选填，默认 HUA179/wuhan-cailanzi
    GH_BRANCH  选填，默认 main
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = "/tmp/cailanzi"

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "HUA179/wuhan-cailanzi")
GH_BRANCH = os.environ.get("GH_BRANCH", "main")
GH_PATH = "data.json"
API = "https://api.github.com/repos/%s/contents/%s" % (GH_REPO, GH_PATH)

# 产出校验阈值：低于这个条数说明抓取链路出了问题，宁可本次失败也不覆盖线上
MIN_ITEMS = 100
MIN_REAL = 30


def _gh(url, method="GET", payload=None, retries=3):
    """GitHub API 调用，带指数退避重试。国内访问 GitHub 偶发超时是常态。"""
    last_err = None
    for i in range(retries):
        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", "Bearer %s" % GH_TOKEN)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "cailanzi-scf")
        if payload is not None:
            req.data = json.dumps(payload).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 404 = 文件不存在，交给调用方处理，重试没有意义
            if e.code == 404:
                raise
            last_err = "HTTP %s %s" % (e.code, e.reason)
            print("[gh] %s，第 %d 次失败" % (last_err, i + 1))
        except Exception as e:
            last_err = "%s: %s" % (type(e).__name__, e)
            print("[gh] %s，第 %d 次失败" % (last_err, i + 1))
        if i < retries - 1:
            time.sleep(3 * (i + 1))
    raise RuntimeError("GitHub API 连续 %d 次失败: %s（%s）" % (retries, url, last_err))


def pull_data_json():
    """拉远端最新 data.json 作为基准，返回文件 sha。"""
    try:
        info = _gh("%s?ref=%s" % (API, GH_BRANCH))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("[pull] 远端还没有 data.json，本次从零构建")
            return None
        raise
    raw = base64.b64decode(info["content"])
    with open(os.path.join(WORK_DIR, GH_PATH), "wb") as f:
        f.write(raw)
    print("[pull] 已拉取远端 data.json，%d 字节，sha=%s" % (len(raw), info["sha"][:8]))
    return info["sha"]


def push_data_json(sha):
    """把本地 data.json 写回仓库。sha 为 None 表示新建文件。"""
    with open(os.path.join(WORK_DIR, GH_PATH), "rb") as f:
        raw = f.read()
    payload = {
        "message": "chore: SCF 全量更新菜价 %s" % time.strftime("%Y-%m-%d %H:%M"),
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": GH_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    res = _gh(API, method="PUT", payload=payload)
    print("[push] 已推送 data.json，新 sha=%s" % res["content"]["sha"][:8])


def verify(local_path):
    """落盘前的内容校验。任何一条不过都直接抛错，不推。"""
    with open(local_path, encoding="utf-8") as f:
        items = json.load(f)

    n = len(items)
    real = sum(1 for i in items if i.get("historyReal"))
    dated = sum(1 for i in items if i.get("historyDates"))
    bad_len = sum(1 for i in items
                  if len(i.get("historyDates") or []) != len(i.get("history") or []))
    print("[check] %d 条 | historyReal %d | 有日期轴 %d | 日期与价格不等长 %d"
          % (n, real, dated, bad_len))

    if n < MIN_ITEMS:
        raise RuntimeError("产出只有 %d 条（阈值 %d），明显异常，放弃推送" % (n, MIN_ITEMS))
    if real < MIN_REAL:
        raise RuntimeError("真实历史仅 %d 条（阈值 %d），发改委大概率没抓到，放弃推送"
                           % (real, MIN_REAL))
    if dated < n:
        raise RuntimeError("%d 条缺 historyDates，放弃推送" % (n - dated))
    if bad_len:
        raise RuntimeError("%d 条 historyDates 与 history 长度不一致，放弃推送" % bad_len)
    return n, real


def main_handler(event, context):
    os.makedirs(WORK_DIR, exist_ok=True)
    os.chdir(WORK_DIR)                 # fetch_data 写相对路径 data.json，落到 /tmp
    sys.path.insert(0, CODE_DIR)

    print("=== SCF 全量抓取开始 ===")
    if not GH_TOKEN:
        raise RuntimeError("缺少环境变量 GH_TOKEN，无法回写仓库")

    sha = pull_data_json()

    import fetch_data
    fetch_data.full_fetch()            # 直接调全量，绕开 main() 的 argv 解析

    local = os.path.join(WORK_DIR, GH_PATH)
    if not os.path.exists(local):
        raise RuntimeError("full_fetch 没有产出 data.json，放弃推送")

    n, real = verify(local)
    push_data_json(sha)
    print("=== SCF 全量抓取完成 ===")
    return {"ok": True, "items": n, "historyReal": real}


# 本地自测入口：python index.py --dry
# 只跑抓取和校验，不碰 GitHub，方便在本机验证逻辑
if __name__ == "__main__":
    if "--dry" in sys.argv:
        os.makedirs(WORK_DIR, exist_ok=True)
        os.chdir(WORK_DIR)
        sys.path.insert(0, CODE_DIR)
        import fetch_data
        fetch_data.full_fetch()
        verify(os.path.join(WORK_DIR, GH_PATH))
        print("[dry] 校验通过，未推送")
    else:
        print("这是 SCF 入口文件，由云函数调用 main_handler；本地测试请加 --dry")
