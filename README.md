# AI 花束平台 · 优化版说明

这次不是只换配色，而是把“推荐 → 选花 → 包装 → 预览 → 生图 → 下单”做成了一条完整链路。
## 一、你提的四点，分别怎么做的

| 需求 | 实现方式 | 代码位置 |
| --- | --- | --- |
| 修改/增加大模型 API，最好审美更好；增加联网 | 统一成 OpenAI 兼容接口，ECNU 与 OpenAI/Qwen 等可切换；联网补充花语/养护作为可选功能，失败自动回退本地库 | `streamlit_app.py` 的「模型调用」「推荐与联网」 |
| 生图不要出现花材不匹配 | 英文花材清单 + 支数 + 颜色 + 包装形态写入提示词；增加“只允许清单内花材”的约束；同时提供按支数精确绘制的 SVG 结构图；可选视觉模型做二次质检 | `bouquet_core.py` 的 `build_image_prompt`、`build_svg_preview` |
| 前端更精美 | 重做主题、Hero、卡片、三步工作台、导航胶囊、移动端适配；去掉原来负 margin 的头部写法 | `streamlit_app.py` 顶部 CSS 与各页面 |
| 增加包材（形状）选项 | 6 种形态 × 6 种包装材质 × 5 种丝带；形态和材质都影响价格、结构图、生图提示词 | `bouquet_core.py` 的 `SHAPE_OPTIONS`、`PACKAGING_OPTIONS` |
| AI 推荐或从当季花材库直接挑 | 新增「当季花材库」页：搜索、类别、颜色、季节、价格、排序、只看当季限定、分页 | `streamlit_app.py` 的 `render_library_page` |

## 二、顺手修掉的问题

1. **灵感卡“一键生成”没有同步侧边栏**：原实现改的是 `st.session_state.target`，但侧边栏 `selectbox` 没有用同名 key，界面不会更新。新版本用 `pending_prefs` 在控件实例化前写入，再自动触发推荐。
2. **香型筛选没有数据支撑**：原知识库没有 `scent` 字段，筛选实际不生效。新版本改为更有数据支撑的“类别 / 颜色 / 季节 / 价格 / 花语关键词”，并给部分花材加了“有香”标签。
3. **生图提示词混入中文花名**：原提示词会生成 “3 玫瑰” 这类中英混合内容。新版本为当前知识库花材补齐英文名，提示词只使用英文清单。
4. **包装费只按尺寸固定计算**：新版本包装费 = 尺寸基础费 + 材质附加费 + 形态附加费，并实时进入总价。
5. **侧边栏高度不够时看不到底部按钮**：新布局把“去工作台 / 清空 / 最近订单”放在固定顺序，并保留 Streamlit 原生侧边栏折叠按钮（不再把 header 整体隐藏）。
6. **卡片点击区域不明确**：原来卡片只是 div，鼠标手型但没有点击行为。新版本每张卡下面都有明确的“加入花篮 / 已加入”按钮。
7. **AI 图生成后刷新丢失**：新版本把图片字节、提示词、配方签名一起保存在 session_state，并支持下载。
8. **订单只存在内存里、无法带走**：新版本订单可下载 JSON / TXT，最近订单还能回填到工作台。
9. **花材只有 emoji、颜色不可选**：新版本接入本地花材照片，并按图片变体提供花色选择；价格明细、结构图、订单和生图提示词都会同步所选颜色。

侧边栏品牌标识使用 7 片几何花瓣组成的抽象花朵：灰粉到梅紫渐变，右上角一片香槟金强调，中心是金色菱形花心；搭配宋体字标和细字距英文，不依赖任何花瓣照片素材。

## 三、文件结构

```text
AI花束平台/
├── streamlit_app.py          # 页面、交互、模型调用
├── bouquet_core.py           # 推荐、计价、提示词、SVG 结构图（纯逻辑）
├── assets_knowledge/
│   ├── knowledge_base/
│   │   └── flower_knowledge.json # 84 种花材，含类别/英文名/季节标签/配色
│   └── assets/flowers/       # 本地花材照片，文件名使用“花材id_颜色码”
├── requirements.txt
├── packages.txt
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example
```

> `streamlit_app.py` 会 `from bouquet_core import ...`，部署时两个 `.py` 文件必须放在同一目录。

## 四、部署与 API 配置

> 推荐配置：**火山方舟 Ark 一站式**（豆包文字 + 豆包视觉 + Seedream 生图），国内网络可访问、一个 Key 即可跑通文字与图片。完整的创建 Key、模型 ID、验证和常见错误说明见 [API配置指南.md](API配置指南.md)。

### 1. Streamlit Cloud 已部署版本

1. 把 `streamlit_app.py`、`bouquet_core.py`、`knowledge_base/flower_knowledge.json` 一起提交到 GitHub。
2. 如果仓库根目录不是这个文件夹，请把 Streamlit Cloud 的 Main file path 指到 `streamlit_app.py`。
3. 在 Streamlit Cloud 的 **Settings → Secrets** 里粘贴 `.streamlit/secrets.toml.example` 的内容并填入真实密钥。
4. 重新部署。

### 2. 本地运行

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

本地把 `.streamlit/secrets.toml.example` 复制成 `.streamlit/secrets.toml`，或者用 `.env`：

```env
ECNU_API_KEY=...
ECNU_API_BASE=https://chat.ecnu.edu.cn/open/api/v1
ECNU_MODEL=ecnu-plus
ECNU_IMAGE_MODEL=ecnu-image
```

### 3. 换成“审美更好”的模型

代码不绑定具体厂商，只要是 OpenAI 兼容的 `/chat/completions` 和 `/images/generations` 即可。把 secrets 换成：

```toml
LLM_API_KEY = "sk-..."
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o"          # 或你账号可用的更强文字模型
IMAGE_API_KEY = "sk-..."
IMAGE_API_BASE = "https://api.openai.com/v1"
IMAGE_MODEL = "gpt-image-1"   # 或 dall-e-3 / 其他兼容生图模型
VISION_MODEL = "gpt-4o"       # 可选：生成后做一致性检查
```

Qwen/DashScope 的兼容模式也可以用于文字与视觉检查；生图接口需要确认是否兼容 `/images/generations`，不兼容时保留结构图与提示词即可。

### 4. 火山方舟 Ark / 豆包 / Seedream

`ARK_API_KEY` 不能单独生效：Ark 的文字和图片都需要指定具体的模型或推理接入点 ID。按需填写：

```toml
ARK_API_KEY = "你的 ARK API Key"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# 豆包文字模型 / 接入点 ID；填了才会优先走 Ark 文字
ARK_MODEL = "你的文字模型或接入点 ID"

# Seedream 图片模型 / 接入点 ID；填了才会走 Ark 生图
ARK_IMAGE_MODEL = "你的图片模型或接入点 ID"
ARK_IMAGE_BASE = "https://ark.cn-beijing.volces.com/api/v3"
```

模型来源的自动优先级是：`LLM_API_KEY`（通用 OpenAI 兼容）→ Ark（有 `ARK_MODEL`）→ ECNU → OpenAI。也可以用 `LLM_PROVIDER = "ecnu" / "ark" / "openai" / "generic"` 强制指定。

侧边栏「⚙️ 模型与额度」会显示当前实际使用的文字/生图来源；如果只填了 `ARK_API_KEY` 而没填模型 ID，会明确提示 Ark 不会生效。

填好配置后，可以在同一个面板点「测试文字模型连接」；它会发一句很短的测试请求，快速验证 Key、Base URL 和模型名是否匹配。生图测试会消耗额度，建议在工作台生成一张图验证。

> 没有配置任何 API 时，应用仍然可用：会自动走本地搭配引擎，结构图、价格、订单都能演示；只是没有 AI 推荐语和 AI 效果图。

AI 灵感页还有一个「联网补充花语灵感（Beta）」开关：勾选后会把维基百科/DuckDuckGo 的花语摘要作为文字参考放进推荐提示词，但候选花材白名单不变，所以不会因为联网结果引入不存在的花材。

## 五、生图“花材不匹配”的处理逻辑

真实文生图模型无法保证 100% 按支数画对，所以这里做了四层保护：

1. **提示词锁定清单**：每种花材用英文名、颜色、支数写进 `Exact flower recipe`，例如 `5 stems of pink Rose; 3 stems of white Lisianthus`。
2. **负向约束**：提示词里明确 `no extra flower species / no substitutions / no duplicated blooms`，如果服务商支持 `negative_prompt`，可在 secrets 里打开 `IMAGE_SUPPORTS_NEGATIVE = "true"`。
3. **精确结构图**：左侧 SVG 按当前花材、支数、包装、形态绘制，不经过 AI，支数和颜色是准确的。它才是“配方”的准确来源。
4. **可选视觉质检**：配置 `VISION_MODEL` 后，生成完会把图片和清单一起发给多模态模型，返回 `match_score / missing / extra`，在页面上显示“视觉质检 87/100，缺少…”。没有配置就跳过，不影响主流程。

页面文案也明确写了：**AI 效果图是风格参考，花材种类与支数以结构图和订单清单为准**。这比承诺“AI 一定画得一模一样”更可靠，答辩时也更好解释。

## 六、包装与价格规则

| 项目 | 规则 |
| --- | --- |
| 尺寸 | S/M/L/XL，影响基础包装费、手工费、默认支数和最大支数 |
| 形态 | 圆形手捧、扇形、韩式单面、方形花盒、手提花篮、瀑布式 |
| 材质 | 韩式雾面纸、牛皮纸、欧根纱、复古报纸、哑光礼盒、无包装 |
| 丝带 | 香槟金、豆沙粉、奶油白、雾霾蓝、酒红 |
| 配送 | 花材+包装+手工 ≥ ¥199 免配送费，否则 ¥15 |
| 预算 | 推荐时会按支数自动调节；工作台可点“压缩到预算内” |

## 七、知识库字段

`flower_knowledge.json` 在原字段基础上补了：

- `category`: 主花 / 配花 / 叶材 / 果材
- `english_name`: 生图提示词和英文展示
- `season_tags`: `["全年"]` 或 `["春季"]` / `["夏季","秋季"]` 等
- `palette`: 用于卡片渐变与 SVG 结构图的十六进制色
- `fragrant`: 是否明显有香（用于标签）
- `care_tip`: 按类别给出的养护提示

新增花材时，最少需要 `id/name/color/language/occasion/target/style/price_level/description/season/unit_price/category/english_name`。`palette` 和 `season_tags` 可以留空，`bouquet_core.enrich_flower` 会自动补。

## 八、建议的验收清单

- [ ] 首页四个灵感卡点任意一个，侧边栏的对象/场合/颜色/风格/预算是否同步，并自动生成搭配。
- [ ] 不填 API Key，点“AI 一键搭配”，是否能走本地引擎并显示花材卡。
- [ ] 去“当季花材库”，切换类别/颜色/价格/只看当季，分页是否正常。
- [ ] 在工作台改支数、角色、形态、包装、丝带，结构图和价格是否实时变化。
- [ ] 点“压缩到预算内”，支数是否下降且总价进入预算。
- [ ] 生成 AI 效果图后，刷新页面图片是否还在（同一会话内）。
- [ ] 提交订单，下载 JSON/TXT，再从侧边栏“最近订单”回填。
- [ ] 手机宽度下，Hero、卡片、按钮是否可读可点。

## 九、还可以继续做的方向

1. **真实订单后台**：现在订单只存在 session，正式比赛演示可以接 Supabase / 飞书多维表格 / 微信小程序后台。
2. **花材图片**：当前已接入本地花材照片和颜色变体；后续可以继续补充/优化 84 种花材的图片、不同角度和更多颜色。
3. **向量检索**：把花语、场合、颜色描述做 embedding，替代关键词打分，推荐会更细腻。
4. **多图方案**：一次生成 2–4 张不同构图，让用户选一张，能显著降低“AI 画错”的挫败感。
5. **库存与季节联动**：接入花店当日库存，缺货花材自动替换并解释原因。
6. **支付与配送轨迹**：接入支付、配送状态、短信通知。
7. **A/B 测试**：对比“AI 先推荐”和“用户先逛花材库”的转化率，决定首页主入口。
