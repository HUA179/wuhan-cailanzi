# 武汉菜篮子 · Wuhan Cai Lan Zi

武汉市 159 个菜品的官方价格监测面板。移动端优先，单文件前端 + Python 多源爬虫，云端每日自动更新。

**线上主地址**：[https://wuhan-cailanzi.pages.dev](https://wuhan-cailanzi.pages.dev)（Cloudflare Pages，监听 `main`）
**线上备份**：[https://hua179.github.io/wuhan-cailanzi/](https://hua179.github.io/wuhan-cailanzi/)（GitHub Pages）

---

## 它显示什么

- **市场均价**：武汉市发改委每日价格 + 农业农村局批发价 + 商务局周报，共 159 个品种
- **商超价格**：真实超市监测点报价（中百仓储、沃尔玛），27 个品种，含「贵 ¥X / 省 ¥X」差价。同一品种取两家监测点中**更便宜的那家**并标出店名，价格相同时中百优先
- **52 周走势**：40 个品种有真实历史回溯，其余按分类价格指数推算（形状真实、绝对价锚定当日实价）
- **来源标注**：每个品种卡片标出具体数据源（发改委·每日 / 农业局·批发 / 商务局·周报）

## 技术栈

| 层 | 方案 |
| --- | --- |
| 前端 | 单文件 `index.html`，Vue 3（Global Build）+ TailwindCSS + ECharts，全 CDN，双击可运行 |
| 数据 | `data.json`，静态 JSON，前端 `fetch` 读取 |
| 爬虫 | `fetch_data.py`，requests + BeautifulSoup + pypinyin |
| 自动化 | GitHub Actions 每日 06:00（北京时间）跑增量更新并提交 |
| 托管 | Cloudflare Pages（主）+ GitHub Pages（备） |

## 快速开始

```bash
git clone https://github.com/HUA179/wuhan-cailanzi.git
cd wuhan-cailanzi
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

本地预览：

```bash
python -m http.server 8000
# 浏览器打开 http://127.0.0.1:8000
```

> 直接双击 `index.html` 也能用，但浏览器对 `file://` 的 `fetch` 有限制，会退回内置演示数据。要看到真实数据必须走 `http.server`。

## 两种抓取模式（重要）

```bash
python fetch_data.py --mode=full     # 本地全量：回溯 52 周真实历史 + 全量品种
python fetch_data.py --mode=daily    # 增量（默认）：只抓今天一个截面
```

> 注意：脚本不解析 `--help`，任何无法识别的参数都会按默认 `daily` 直接跑一次真实抓取并写 `data.json`。想看帮助请读源码 `main()`，不要在正式目录里试探。

**为什么分两种**：武汉市发改委接口是裸 IP `58.48.136.167:7600`，**境外不可达**（ConnectTimeout 20s）。GitHub Actions 的机器在境外，抓不到这条主源，所以：

- **云端**只跑 `--mode=daily`，把今天的新价追加到 52 周序列末尾、淘汰最老一周、重算百分位。请求数个位数，几秒跑完。
- **本地**需要定时跑 `--mode=full`（建议每周一次），把发改委那 40 个品种的真实历史和商超价刷新，然后 `git push`。

## 数据源

| 来源 | 品种数 | 频率 | 说明 |
| --- | --- | --- | --- |
| 武汉市发改委「价格监测平台」 | 40 | 每日 | 提供真实 52 周历史 + 7 家超市监测点报价。**仅境内可达** |
| 武汉市农业农村局 | 112 | 每日 | 批发价，`nyncj.wuhan.gov.cn`，HTTPS 稳定 |
| 武汉市商务局 | 7 | 每周 | 批发市场周报，肉禽蛋补充 |

## 目录结构

```
index.html                           前端（单文件，全部逻辑内联）
fetch_data.py                        多源爬虫（--mode=full / daily）
data.json                            数据（159 条，每条 52 周 history）
requirements.txt                     依赖（只有 3 个第三方包）
.github/workflows/update-price.yml   每日自动更新
```

## data.json 结构

```json
{
  "id": 1,
  "name": "丝瓜",
  "rawName": "丝瓜",
  "pinyin": "sg",
  "category": "蔬菜",
  "unit": "500g",
  "currentPrice": 5.42,
  "supermarketPrice": null,
  "storeName": "",
  "yearPosition": 62,
  "history": [52 个数字],
  "historyReal": true,
  "prevObs": 5.1,
  "prevObsAge": 1,
  "obsWeeks": 52,
  "source": "武汉市发改委",
  "updated": "2026-10-21"
}
```

`historyReal` 区分真实历史与指数推算；`prevObs` / `prevObsAge` 用于识别季节性品种停报后复出（避免误判为暴涨）。

## 数据健康机制

- `price_sane()`：日涨跌超 `+120%` / `-55%` 且非长期停报后复出，判定脏数据，跳过更新保留旧值
- `restore_fgj_items()`：全量模式遇到发改委不可达时，从旧 `data.json` 继承发改委品种，防止降级数据覆盖真实历史
- 拆成 `index_fgj` / `index_supp` 两套索引：发改委是零售价、农业局是批发价，同名品种（如「花菜」1.5 vs 3.97）混用会污染数据
- `pick_cheapest_supermarket()`：商超价两店比价取最低，`storeName` 记该店，价格相同时中百优先。full 与 daily 共用同一套口径，避免两端互相覆盖；比较只在**本轮抓到的数据**内进行，不拿上一轮的旧价参与
- 价格 52 周波动 < 1.5% 的品种（如政府定价的米面）前端显示「价格平稳」，不显示误导性的 100% 高位

## 注意

- 仓库开启 `core.autocrlf=true`，工作区是 CRLF、git blob 是 LF。跨机器比 md5 会误判不一致，请比对内容。
- 抓取失败时脚本**不会**覆盖 `data.json`，只在确实拿到数据时才写文件。
