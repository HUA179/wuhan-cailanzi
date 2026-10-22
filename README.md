# 武汉菜篮子 · Wuhan Cai Lan Zi

武汉市 180 个品种（本地菜价 + 全国参考）的官方价格监测面板。移动端优先，单文件前端 + Python 多源爬虫，云端每日自动更新。

**线上主地址**：[https://wuhan-cailanzi.pages.dev](https://wuhan-cailanzi.pages.dev)（Cloudflare Pages，监听 `main`）
**线上备份**：[https://hua179.github.io/wuhan-cailanzi/](https://hua179.github.io/wuhan-cailanzi/)（GitHub Pages）

---

## 它显示什么

- **市场均价**：武汉市发改委每日价格 + 农业农村局批发价 + 商务局周报，共 159 个本地品种
- **水果**：11 个 —— 全国口径 6 种（富士苹果/巨峰葡萄/香蕉/菠萝/西瓜/鸭梨）+ 全国水果均价 + 新发地分品种（苹果/香蕉/西瓜/**橘子**）
- **全国参考**：17 个 —— 农业农村部周报分品种水果 + 日报全国均价基准（蔬菜/水果/猪肉/牛肉/羊肉/鸡蛋/白条鸡/鲫鱼/鲤鱼/白鲢鱼/大带鱼）
- **商超价格**：真实超市监测点报价（中百仓储、沃尔玛），27 个品种，含「贵 ¥X / 省 ¥X」差价。同一品种取两家监测点中**更便宜的那家**并标出店名，价格相同时中百优先
- **52 周走势**：61 个品种有真实历史回溯（其中 11 个 52 周零缺口），其余按分类价格指数推算（形状真实、绝对价锚定当日实价）
- **来源标注**：每个品种卡片标出具体数据源（发改委·每日 / 农业局·批发 / 商务局·周报 / 全国·参考 / 新发地·批发）
- **单位分口径**：本地零售 `元/500g`，全国参考与新发地 `元/公斤`（批发），卡片上按品种显示，前端不假设统一单位

## 技术栈

| 层 | 方案 |
| --- | --- |
| 前端 | 单文件 `index.html`，Vue 3（Global Build）+ ECharts + 预编译 Tailwind CSS，**依赖全部本地化，不请求任何公共 CDN** |
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

> 直接双击 `index.html` 样式和脚本都正常，但浏览器禁止 `file://` 页面 `fetch` 本地文件，`data.json` 读不到，页面顶部会出现黄色提示条并退回 6 条演示数据。**要看到真实数据必须起本地服务**，或者直接访问线上站点。

## 两种抓取模式（重要）

```bash
python fetch_data.py --mode=full             # 全量：回溯 52 周真实历史 + 全量品种
python fetch_data.py --mode=daily            # 增量（默认）：只抓今天一个截面
python fetch_data.py --city=wuhan --mode=full # 指定城市（默认读 CAILANZI_CITY，再退回 wuhan）
python -m unittest discover -s tests -v       # 离线单元测试（不联网，19 项）
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
| 农业农村部「全国农产品批发市场价格信息系统」 | 17 | 每周/每日 | 周报 246 期（分品种水果，元/公斤）+ 日报 1369 期（全国均价基准）。`pfsc.agri.cn` |
| 北京新发地 | 4 | 每日 | 分品种水果日价，元/斤 ×2 转元/公斤，补上官方 6 种水果里没有的**橘子** |

**湖北这一层怎么处理**：武汉是湖北省会，一律标「湖北·武汉」，**不虚构全省均价**。省级官方价格抓不到（湖北省发改委 `fgw.hubei.gov.cn` 是瑞数 WAF 动态防护，HTTP 412，不逆向不破解），所以用「武汉实测 + 全国参考」满足补数据量的需求，商业数据源（惠农网等）不接。

## 目录结构

```
index.html                           前端（单文件，全部逻辑内联）
lib/vue.global.prod.js               Vue 3.4.31 运行时（本地副本）
lib/echarts.min.js                   ECharts 5.5.1 运行时（本地副本）
lib/tailwind.css                     预编译样式（15 KB，只含页面用到的类）
tools/tailwind/                      Tailwind 构建配置（改类名后要重新编译）
fetch_data.py                        主流程（--mode=full / daily，--city=xxx）
cities/base.py                       城市配置基座（必填校验 + 默认值）
cities/wuhan.py                      武汉：站点参数 / 分类映射 / 名称归一 / 源开关
cities/__init__.py                   load_city()：按 id 载入 cities/<id>.py
sources/agri_national.py             农业农村部全国周报 + 日报
sources/xinfadi.py                   北京新发地分品种水果
sources/variety_map.py               新发地「具体品种名 → 品类」白名单映射
tests/test_sources.py                离线单元测试（映射表 / 表5解析 / 日报抽数 / 城市配置）
data.json                            数据（180 条，每条 52 周 history）
requirements.txt                     依赖（只有 3 个第三方包）
.github/workflows/update-price.yml   每日自动更新
```

### 前端依赖为什么不走 CDN

早期用 `cdn.jsdelivr.net` 和 `cdn.tailwindcss.com`，结果在手机 QQ、夸克、必应浏览器里**整页空白**——这些环境会拦截境外 CDN，Vue 加载失败导致 `v-cloak` 永远不解除，页面就一直是背景色。现在三个依赖全部落在 `lib/`，`index.html` 里零外链，断网也能正常渲染。

**Tailwind 的处理方式**：不用浏览器端编译版（`cdn.tailwindcss.com` 那 400 KB 的 JIT 运行时），改成构建期编译成静态 CSS，只保留页面实际用到的类，**15 KB**。

改了 `index.html` 里的 Tailwind 类名后必须重新编译，否则新类不生效：

```bash
cd tools/tailwind
npm i                      # 只装 tailwindcss 一个开发依赖，约 10 秒
npm run build              # 输出到 ../../lib/tailwind.css
```

`lib/` 下的三个文件建议提交进仓库：站点是纯静态托管，没有构建流水线，运行时必须有这些文件。

### 换城市怎么做

```bash
cp cities/wuhan.py cities/shanghai.py     # 改 id/name/area_code/站点地址
python fetch_data.py --city=shanghai --mode=full
```

`fetch_data.py` 里没有任何写死的城市常量，站点地址、行政区划码、分类映射、名称归一、参考源开关全部来自城市配置。**但要诚实说明**：配置能覆盖的是「同一类数据源换个城市参数」；如果新城市用的是完全不同的政务站点（HTML 结构不同），仍需在 `sources/` 下新写一个抓取模块 —— 那部分不是配置能抽象掉的。换城市真正的难点从来不是代码，而是新城市有没有可回溯的公开历史数据。

## data.json 结构

```json
{
  "id": 1,
  "name": "丝瓜",
  "rawName": "丝瓜",
  "pinyin": "sg",
  "category": "蔬菜",
  "unit": "500g",
  "unitLabel": "元/500g",
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

参考源品种（全国参考 / 新发地）额外带四个字段：

```json
{
  "unit": "kg",
  "unitLabel": "元/公斤",
  "source": "全国参考",
  "sourceDetail": "农业农村部 · 全国农产品批发市场价格信息系统",
  "region": "national",        // wuhan / beijing / national
  "granularity": "weekly",     // weekly / daily
  "dataLevel": "official"
}
```

### 诚实性约定（全程有效）

- 官方某周没发数据 → 该点 `null`，图上断口、不连线、不插值、不前向填充
- 断档超过 4 周的品种前端降级为「实测 N 周」，不给位置百分位
- 新发地品种名映射不到就**不计入**（当日该品类少一条报价），绝不猜；未映射清单打在日志里备查
- 不生成任何随机/模拟历史（旧版的 `gen_history()` 已删除）

## 数据健康机制

- `price_sane()`：日涨跌超 `+120%` / `-55%` 且非长期停报后复出，判定脏数据，跳过更新保留旧值
- `restore_fgj_items()`：全量模式遇到发改委不可达时，从旧 `data.json` 继承发改委品种，防止降级数据覆盖真实历史
- 拆成 `index_fgj` / `index_supp` 两套索引：发改委是零售价、农业局是批发价，同名品种（如「花菜」1.5 vs 3.97）混用会污染数据
- `pick_cheapest_supermarket()`：商超价两店比价取最低，`storeName` 记该店，价格相同时中百优先。full 与 daily 共用同一套口径，避免两端互相覆盖；比较只在**本轮抓到的数据**内进行，不拿上一轮的旧价参与
- 价格 52 周波动 < 1.5% 的品种（如政府定价的米面）前端显示「价格平稳」，不显示误导性的 100% 高位
- 新发地单位闸门：`unitInfo` 既不是「斤」也不是空（如按「箱」卖）→ 跳过，不做猜测换算
- 单测覆盖两条踩过的坑：黑名单若写成单字「籽」会误杀 `无籽西瓜`，写成「糖」会误杀 `金秋砂糖桔`

## 注意

- 仓库开启 `core.autocrlf=true`，工作区是 CRLF、git blob 是 LF。跨机器比 md5 会误判不一致，请比对内容。
- 抓取失败时脚本**不会**覆盖 `data.json`，只在确实拿到数据时才写文件。
