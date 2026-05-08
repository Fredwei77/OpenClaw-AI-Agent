# Design Reference Index

OpenClaw AI Agent 的审美参考库。来源: [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)

每个 DESIGN.md 包含 9 个标准章节: Visual Theme, Color Palette, Typography, Components, Layout, Depth, Do's/Don'ts, Responsive, Agent Prompt Guide。

## 选用指南

| 场景 | 推荐参考 | 理由 |
|------|----------|------|
| **后台 Dashboard / 数据面板** | `linear.md` | 深色主题、数据密集型布局、四层 surface 阶梯 |
| **电商产品页 / 落地页** | `shopify.md` | 电商基因、深色戏剧感、产品截图展示模式 |
| **支付流程 / 金融数据** | `stripe.md` | 精密间距、蓝色调阴影、表格数字等宽显示 |
| **SaaS 定价页 / 功能对比** | `notion.md` | 四档定价对比、彩色功能卡片、8px 圆角矩形按钮 |
| **极简首页 / 开发者工具** | `vercel.md` | 纯白画布、shadow-as-border、Geist 字体体系 |
| **开发者平台 / API 文档** | `supabase.md` | 深色原生、emerald 品牌色、HSL alpha 分层 |

## 文件清单

| 文件 | 品牌 | 主题 | 关键色 |
|------|------|------|--------|
| `shopify.md` | Shopify | 深色电商 | Neon Green `#36F4A4` |
| `stripe.md` | Stripe | 白底金融 | Purple `#533afd` |
| `linear.md` | Linear | 近黑面板 | Lavender `#5e6ad2` |
| `vercel.md` | Vercel | 极简白底 | Black `#171717` |
| `notion.md` | Notion | 编辑器风格 | Purple `#5645d4` |
| `supabase.md` | Supabase | 深色开发者 | Emerald `#3ecf8e` |

## 快速对照

### 字体系统

| 品牌 | Display 字体 | Body 字体 | Mono 字体 |
|------|-------------|-----------|-----------|
| Shopify | NeueHaasGrotesk (330–400) | Inter Variable (400–550) | ui-monospace |
| Stripe | sohne-var (300, ss01) | sohne-var (300–400) | SourceCodePro |
| Linear | Linear Display (500–600) | Linear Text (400) | Linear Mono |
| Vercel | Geist Sans (600) | Geist Sans (400–500) | Geist Mono |
| Notion | Notion Sans (600) | Notion Sans (400–500) | — |
| Supabase | Circular (400) | Circular (400–500) | Source Code Pro |

### 圆角策略

| 品牌 | 按钮 | 卡片 | 标签/徽章 |
|------|------|------|-----------|
| Shopify | 9999px (pill) | 8–12px | 4px |
| Stripe | 4px | 4–8px | 4px |
| Linear | 8px | 12px | 9999px (pill) |
| Vercel | 6px | 8px | 9999px (pill) |
| Notion | 8px (矩形) | 12px | 6px / 9999px |
| Supabase | 9999px (pill) | 8–16px | 9999px (pill) |

### 深度/阴影策略

| 品牌 | 方法 |
|------|------|
| Shopify | 多层 box-shadow + inset 白色辉光 |
| Stripe | 蓝色调阴影 `rgba(50,50,93,0.25)` |
| Linear | 无阴影，靠 surface 阶梯 + hairline 边框 |
| Vercel | shadow-as-border `0px 0px 0px 1px rgba(0,0,0,0.08)` |
| Notion | 标准阴影层级 0–4 |
| Supabase | 无阴影，靠 border 颜色差异 |

## 使用方式

Agent 在生成 UI 代码时，应根据上下文选择对应的设计参考文件，遵循其中的:
- 颜色 token（直接使用 hex 值）
- 字体层级（size/weight/line-height/letter-spacing）
- 组件规范（按钮、卡片、输入框等）
- 间距系统（base unit + scale）
- Do's and Don'ts 约束

## 扩展

完整设计库包含 70+ 品牌，可在 [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md/tree/main/design-md) 浏览更多。可按需下载到本目录。
