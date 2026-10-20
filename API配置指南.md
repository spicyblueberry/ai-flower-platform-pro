# 信心花舍 · API 配置指南（推荐版）

## 推荐方案：火山方舟 Ark 一站式

推荐用**火山方舟 Ark** 同时承担文字推荐、视觉质检和花束生图：

- 文字 / 视觉：豆包系列模型，中文表达自然，支持多模态输入。
- 生图：Seedream 系列，花材细节和商业摄影感比较好。
- 一个 Key、一个 Base URL，文字接口和图片接口都是项目当前已经适配的 OpenAI 兼容格式。
- 国内网络可访问，适合比赛现场演示。

如果你更看重海外模型的审美，可以把文字/生图换成 OpenAI（见文末备选）。

## 一、创建 ARK API Key

1. 打开火山引擎控制台：<https://console.volcengine.com/ark>
2. 注册/登录并完成实名认证。
3. 进入「火山方舟」控制台。
4. 找到「API Key 管理」→「创建 API Key」。
5. 复制生成的 Key。它通常只完整显示一次，请先保存到密码管理器。
6. Base URL 使用：`https://ark.cn-beijing.volces.com/api/v3`

## 二、开通模型并拿到模型 ID

在方舟控制台里：

1. 进入「开通管理」/「模型广场」，开通豆包文字模型、豆包视觉模型（可选）和 Seedream 图片模型。
2. 进入「在线推理」/「模型推理」/「接入点」页面。
3. 复制**模型 ID**，或创建一个**推理接入点**并复制 `ep-...` 形式的接入点 ID。
4. 文字模型 ID 填到 `ARK_MODEL`；图片模型 ID 填到 `ARK_IMAGE_MODEL`。

> 模型 ID 会随账号、地域和开通时间变化，代码里不写死。请以控制台实际显示为准。

官方文档：<https://www.volcengine.com/docs/82379>

## 三、填入 secrets

本地运行：

1. 把 `.streamlit/secrets.toml.example` 复制为 `.streamlit/secrets.toml`。
2. 填入真实的 Key 和模型 ID。

Streamlit Cloud：

1. 打开应用的 **Settings → Secrets**。
2. 粘贴下面这份 TOML。
3. 保存并重新部署。

```toml
ARK_API_KEY = "真实 ARK Key"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

ARK_MODEL = "你的豆包文字模型或接入点 ID"
ARK_IMAGE_MODEL = "你的 Seedream 图片模型或接入点 ID"
ARK_IMAGE_BASE = "https://ark.cn-beijing.volces.com/api/v3"

LLM_PROVIDER = "ark"

# 可选：视觉一致性检查（需要豆包视觉模型/接入点 ID）
# VISION_MODEL = "你的豆包视觉模型或接入点 ID"

# 如果 Seedream 报 response_format 不支持，改成 "false"
# IMAGE_SEND_RESPONSE_FORMAT = "true"
```

## 四、在应用内验证

打开左侧「⚙️ 模型与额度」：

- 应显示 `文字：Ark / 豆包 · 你的模型 ID`
- 应显示 `生图：Ark / Seedream · 你的图片模型 ID`
- 点「测试文字模型连接」。如果返回连接正常，说明 Key、Base URL、模型名都可用。
- 生图验证请在工作台点「🎨 生成 AI 效果图」。这会实际消耗一次生图额度，所以没有做自动测试按钮。

## 五、常见错误

| 状态 | 常见原因 | 处理 |
| --- | --- | --- |
| 401 | Key 错误、过期或复制时带了空格 | 重新创建/复制 API Key |
| 403 | 模型未开通、账号无权限 | 在方舟控制台开通对应模型 |
| 404 | Base URL 或模型 ID 不对 | 检查 `/api/v3` 和模型/接入点 ID |
| 429 | 频率或额度超限 | 稍后重试，或查看账户额度 |
| 400 response_format | 图片接口不接受该字段 | 设置 `IMAGE_SEND_RESPONSE_FORMAT = "false"` |

## 六、备选方案

### OpenAI

适合有海外网络和支付方式的账号：

```toml
LLM_API_KEY = "sk-..."
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"

IMAGE_API_KEY = "sk-..."
IMAGE_API_BASE = "https://api.openai.com/v1"
IMAGE_MODEL = "gpt-image-1"

VISION_MODEL = "gpt-4o"
```

创建 Key：<https://platform.openai.com/api-keys>

### 华东师大 ECNU

适合作为文字备选；图片是否可用取决于学校账号是否开放 `ecnu-image` 权限。

```toml
ECNU_API_KEY = "真实 ECNU Key"
ECNU_API_BASE = "https://chat.ecnu.edu.cn/open/api/v1"
ECNU_MODEL = "ecnu-plus"
ECNU_IMAGE_MODEL = "ecnu-image"
```

### 阿里云百炼 Qwen

适合文字/视觉；生图接口不是本项目的默认适配方式，建议图片继续用 Ark Seedream。

```toml
LLM_API_KEY = "sk-..."
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen-plus"
VISION_MODEL = "qwen-vl-max"
```

控制台：<https://bailian.console.aliyun.com/>

## 七、安全提醒

- 真实 Key 只放在 `.streamlit/secrets.toml` 或 Streamlit Cloud Secrets。
- 不要把 `.streamlit/secrets.toml` 提交到 GitHub。
- 不要把 Key 截图发到公开群聊；如果不小心泄露，立即在控制台删除并重建。
