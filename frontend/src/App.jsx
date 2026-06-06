import { useState, useRef, useEffect, useCallback } from 'react';
import { LayoutDashboard, Users, Send, Settings, Search, Activity, Box, BarChart3, Loader2, Sparkles, Terminal, Bot, X, Send as SendIcon, Globe, Blocks, Key, TrendingUp, CheckCircle, RefreshCw, Trash2, Eye } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import ReactMarkdown from 'react-markdown';

// Use environment variable for backend URL if available, default to localhost:8000
const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://127.0.0.1:8000';

// Decode JWT payload without verifying signature (client-side only)
function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(c =>
      '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
    ).join(''));
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

// Safely coerce a value to an array (handles string, null, undefined)
function toArray(val) {
  if (Array.isArray(val)) return val;
  if (typeof val === 'string' && val.trim()) return [val];
  return [];
}

function isTokenValid(token) {
  if (!token) return false;
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return false;
  // Check if token expires within the next 60 seconds
  return payload.exp > (Date.now() / 1000) + 60;
}

const i18n = {
  en: {
    brand: "OpenClaw AI",
    tabDashboard: "Nexus Overview",
    tabLeads: "Lead Extractor",
    tabMarketing: "Marketing Engine",
    tabAnalytics: "Growth Analytics",
    tabPlugins: "Plugin Ecosystem",
    tabSkills: "Skill Modules",
    tabSettings: "System Config",
    headerDashboard: "Nexus Overview",
    headerLeads: "Lead Extraction Agent",
    serverIntegrity: "Server Integrity",
    statsTotalLeads: "Total Leads Extracted",
    statsHealth: "System Health",
    statsHealthValue: "Optimal",
    statsDroids: "Active Droids",
    panelAcquisition: "Target Acquisition Parameters",
    platformX: "X (Twitter)",
    platformLinkedIn: "LinkedIn Matrix",
    platformShopify: "Shopify Network",
    keywordPlaceholder: "Enter niche keyword (e.g. fitness equipment)",
    btnScraping: "Mining Data...",
    btnDeploy: "Deploy Extractor",
    panelStream: "Neural Data Stream",
    thPlatform: "Platform",
    thIdentity: "Account Identity",
    thLink: "Neural Link",
    thTarget: "Target Variables",
    emptyScraping: "Synapses establishing connection...",
    emptyStandby: "Grid is empty. Standby for extraction deployment.",
    drawerTitle: "MARKETING AI",
    chatGreeting: "Greetings! I am the OpenClaw Nexus AI. Need help generating marketing templates for your newly extracted leads?",
    chatPlaceholder: "Command the AI...",
    sysError: "[System Error] Neural link severed. Cannot connect to LLM core.",
    sysInit: "[System] Initializing headless browser for ",
    sysSuccess: "[Success] Scraped ",
    sysSuccessEnd: " leads targeting ",
    sysErrorNet: "[Error] Network failed: Could not connect to the Backend API. Make sure FastAPI is running on port 8000.",
    offlineTitle: "MODULE OFFLINE",
    offlineDesc1: "The [",
    offlineDesc2: "] neural sector is currently under construction.",
    offlineDesc3: "Standby for the impending protocol download in upcoming patches.",
    dashConnected: "Nexus Network Connected",
    dashNominal: "All system metrics nominal. Navigate to Lead Extractor to commence operations.",
    pluginSearch: "Search installed plugins...",
    pluginActive: "Active",
    pluginInactive: "Inactive",
    pluginEnable: "Enable",
    pluginDisable: "Disable",
    pluginBrowse: "Browse Marketplace...",
    settingsApiKey: "API Key Management",
    settingsUpdateKey: "Update Key",
    settingsAgent: "AI Agent Settings",
    settingsLlm: "Default LLM",
    settingsConcurrent: "Max Concurrent Scrapers",
    settingsNetwork: "Network & Webhooks",
    settingsTestConn: "Test Connection",
    settingsTesting: "Testing...",
    settingsSuccess: "Connected",
    marketTitle: "Plugin Marketplace",
    pluginInstall: "Install",
    pluginInstalled: "Installed",
    pipelineTitle: "Full Marketing Pipeline",
    pipelineDesc: "Research Agent + Chat Agent: analyze leads, generate multi-channel messages",
    pipelineTag: "Pipeline",
    pipelineRunning: "Pipeline processing...",
    pipelineResearch: "Research Agent analyzing leads...",
    pipelineChat: "Chat Agent generating messages...",
    pipelineDone: "Pipeline complete",
    pipelineCopyAll: "Copy All",
    pipelineTier: "Tier",
    pipelineScore: "Score",
    pipelineMessages: "Messages",
    pipelineSummary: "Pipeline Summary",
    pipelineHighTier: "High",
    pipelineMidTier: "Medium",
    pipelineLowTier: "Low",
    pipelineEmail: "Email",
    pipelineLinkedIn: "LinkedIn DM",
    pipelineTwitter: "Twitter DM",
    skillRun: "Run Skill",
    skillRunning: "Executing...",
    skillInputPlaceholder: "Enter text, keywords, or paste data for the skill to process...",
    skillResult: "Result",
    skillCopy: "Copy",
    skillCopied: "Copied",
    skillInputRequired: "Please enter some input text for the skill",
    skillLoginRequired: "Please log in first"
  },
  zh: {
    brand: "OpenClaw 智爪",
    tabDashboard: "枢纽总览",
    tabLeads: "线索捕获器",
    tabMarketing: "营销引擎",
    tabAnalytics: "增长分析",
    tabPlugins: "插件网络",
    tabSkills: "Skill 技能树",
    tabSettings: "系统配置",
    headerDashboard: "枢纽总览",
    headerLeads: "线索提取特工",
    serverIntegrity: "服务器状态",
    statsTotalLeads: "已提取线索总数",
    statsHealth: "系统健康度",
    statsHealthValue: "极佳",
    statsDroids: "活跃无人机",
    panelAcquisition: "目标捕获参数",
    platformX: "X (推特)",
    platformLinkedIn: "领英矩阵",
    platformShopify: "Shopify 网络",
    keywordPlaceholder: "输入垂直领域关键词 (例: 健身器材)",
    btnScraping: "数据挖掘中...",
    btnDeploy: "部署提取器",
    panelStream: "神经数据流",
    thPlatform: "平台",
    thIdentity: "账户标识",
    thLink: "神经链接",
    thTarget: "目标变量",
    emptyScraping: "突触连接建立中...",
    emptyStandby: "网格为空。待机等待提取任务部署。",
    drawerTitle: "营销智能体",
    chatGreeting: "您好！我是 OpenClaw 枢纽 AI。需要帮您为新提取的客户线索生成营销邮件或话术模板吗？",
    chatPlaceholder: "向 AI 发送指令...",
    sysError: "[系统错误] 神经链接已断开，无法连接到 LLM 核心接口。",
    sysInit: "[系统] 正在初始化无头浏览器，目标平台: ",
    sysSuccess: "[成功] 共抓取 ",
    sysSuccessEnd: " 条线索，目标关键词: ",
    sysErrorNet: "[错误] 网络故障：无法连接到后端 API。请确保 FastAPI 正在本地 8000 端口运行。",
    offlineTitle: "核心模块离线",
    offlineDesc1: "【",
    offlineDesc2: "】神经突触扇区目前正在建设中。",
    offlineDesc3: "请持续关注后续版本更新的协议下发。",
    dashConnected: "智爪中枢网络已连接",
    dashNominal: "各项系统指标正常。请导航至「线索捕获器」执行提取任务。",
    pluginSearch: "搜索已安装的插件...",
    pluginActive: "已运行",
    pluginInactive: "未启用",
    pluginEnable: "启用",
    pluginDisable: "停用",
    pluginBrowse: "浏览插件市场...",
    settingsApiKey: "API 密钥管理",
    settingsUpdateKey: "更新密钥",
    settingsAgent: "AI 代理配置",
    settingsLlm: "默认运行模型",
    settingsConcurrent: "最大并发执行上限",
    settingsNetwork: "网络与 Webhook 回传",
    settingsTestConn: "测试连接",
    settingsTesting: "测试中...",
    settingsSuccess: "连接成功",
    marketTitle: "插件发现市场",
    pluginInstall: "安装",
    pluginInstalled: "已安装",
    pipelineTitle: "全自动营销管道",
    pipelineDesc: "Research Agent + Chat Agent：深度分析线索，自动生成多渠道营销消息",
    pipelineTag: "全自动化",
    pipelineRunning: "管道处理中...",
    pipelineResearch: "Research Agent 正在分析线索...",
    pipelineChat: "Chat Agent 正在生成消息...",
    pipelineDone: "管道执行完成",
    pipelineCopyAll: "全部复制",
    pipelineTier: "层级",
    pipelineScore: "评分",
    pipelineMessages: "消息",
    pipelineSummary: "管道摘要",
    pipelineHighTier: "高意向",
    pipelineMidTier: "中意向",
    pipelineLowTier: "低意向",
    pipelineEmail: "邮件",
    pipelineLinkedIn: "领英私信",
    pipelineTwitter: "推特私信",
    skillRun: "执行技能",
    skillRunning: "执行中...",
    skillInputPlaceholder: "输入文本、关键词或粘贴数据，供技能处理...",
    skillResult: "执行结果",
    skillCopy: "复制",
    skillCopied: "已复制",
    skillInputRequired: "请输入技能所需的文本内容",
    skillLoginRequired: "请先登录"
  }
};

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [keyword, setKeyword] = useState('fitness equipment');
  const [platform, setPlatform] = useState('x');
  const [isScraping, setIsScraping] = useState(false);
  const [leads, setLeads] = useState([]);
  const [statusMsg, setStatusMsg] = useState('');
  const [leadsLoading, setLeadsLoading] = useState(false);
  const [leadsSearch, setLeadsSearch] = useState('');
  const [leadStatusFilter, setLeadStatusFilter] = useState('');
  const [leadTotal, setLeadTotal] = useState(0);
  const [leadDetails, setLeadDetails] = useState(null);

  // Auth State
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [loginError, setLoginError] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [registerName, setRegisterName] = useState('');
  
  // Marketing Engine State
  const [marketingLoading, setMarketingLoading] = useState(false);
  const [marketingResult, setMarketingResult] = useState('');
  const [marketingActionTitle, setMarketingActionTitle] = useState('');

  // Marketing Pipeline State
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [pipelineStep, setPipelineStep] = useState('');
  const [expandedLead, setExpandedLead] = useState(null);
  const [marketingCampaigns, setMarketingCampaigns] = useState([]);
  const [campaignsLoading, setCampaignsLoading] = useState(false);
  const [campaignsError, setCampaignsError] = useState('');

  // i18n Language State
  const [lang, setLang] = useState('zh');
  const t = i18n[lang];

  // AI Assistant State
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: t.chatGreeting }
  ]);
  const [isTyping, setIsTyping] = useState(false);

  // Plugin State
  const [pluginSearchQuery, setPluginSearchQuery] = useState('');
  const [skillSearchQuery, setSkillSearchQuery] = useState('');
  const [skillRunning, setSkillRunning] = useState(null);
  const [skillResult, setSkillResult] = useState(null);
  const [skillInput, setSkillInput] = useState('');
  const [selectedSkill, setSelectedSkill] = useState(null);
  const [plugins, setPlugins] = useState([
    { id: 'plugin-1', name: 'Lead Scraper Core', version: 'v1.2', descEn: 'Core scraping plugin supporting multiple platforms.', descZh: '核心线索爬取插件，支持 X/LinkedIn 等平台。', icon: 'Box', color: 'var(--primary)', isActive: true },
    { id: 'plugin-2', name: 'Marketing LLM', version: 'v2.0', descEn: 'Smart marketing copy generation interface.', descZh: '智能营销文案生成模型接口及提示词工程。', icon: 'Bot', color: 'var(--accent)', isActive: true },
    { id: 'plugin-3', name: 'Shopify Store Inspector', version: 'v1.0', descEn: 'Deep scan Shopify stores for owner contact info.', descZh: '深度扫描 Shopify 店铺以获取店主联系信息。', icon: 'Search', color: 'var(--success)', isActive: false },
  ]);

  const [isMarketplaceOpen, setIsMarketplaceOpen] = useState(false);
  const [marketPlugins, setMarketPlugins] = useState([
    { id: 'plugin-4', name: 'Discord Sentinel', version: 'v1.5', descEn: 'Intercept intent messages in crypto/NFT communities.', descZh: '拦截 Web3/NFT 兴趣社区中的高意向发言。', icon: 'Terminal', color: '#8b5cf6', isActive: false },
    { id: 'plugin-5', name: 'GitHub Repo Monitor', version: 'v0.9', descEn: 'Extract tech leads from stargazers and issues.', descZh: '从 Stargazers 或特定 Issue 中挖掘技术选型客户。', icon: 'Blocks', color: '#facc15', isActive: false }
  ]);

  // Runtime status is read-only: local configuration is managed through .env.
  const [systemStatus, setSystemStatus] = useState(null);
  const [systemStatusLoading, setSystemStatusLoading] = useState(false);
  const [systemStatusError, setSystemStatusError] = useState('');

  // Lead Scraper Extended Params
  const [selectedGeo, setSelectedGeo] = useState('all');
  const [selectedFollowers, setSelectedFollowers] = useState('all');
  const [selectedContentType, setSelectedContentType] = useState('all');
  const [maxResults, setMaxResults] = useState(50);

  // Dashboard Tab Data
  const dashboardQuickActions = [
    { labelZh: '部署线索提取器', labelEn: 'Deploy Extractor', icon: <Search size={18} />, color: 'var(--primary)', tab: 'leads' },
    { labelZh: '启动营销引擎', labelEn: 'Launch Marketing', icon: <Send size={18} />, color: 'var(--accent)', tab: 'marketing' },
    { labelZh: '执行技能模块', labelEn: 'Run Skill Module', icon: <Sparkles size={18} />, color: '#8b5cf6', tab: 'skills' },
    { labelZh: '管理插件生态', labelEn: 'Manage Plugins', icon: <Blocks size={18} />, color: 'var(--success)', tab: 'plugins' },
  ];
  const runtimeTime = systemStatus?.updated_at ? new Date(systemStatus.updated_at).toLocaleTimeString() : '--:--:--';
  const componentReady = systemStatus?.components || {};
  const dashboardSystemLogs = [
    { time: runtimeTime, msg: lang === 'zh' ? `[系统] 工作台状态: ${systemStatus?.status || '正在加载'}` : `[System] Workbench status: ${systemStatus?.status || 'loading'}`, type: systemStatus?.status === 'healthy' ? 'success' : 'info' },
    { time: runtimeTime, msg: lang === 'zh' ? `[数据库] PostgreSQL ${componentReady.database ? '已连接' : '未就绪'}` : `[Database] PostgreSQL ${componentReady.database ? 'connected' : 'not ready'}`, type: componentReady.database ? 'success' : 'info' },
    { time: runtimeTime, msg: lang === 'zh' ? `[队列] 等待 ${systemStatus?.task_queue?.queue_size ?? '-'} · 执行中 ${systemStatus?.task_queue?.active_tasks ?? '-'}` : `[Queue] pending ${systemStatus?.task_queue?.queue_size ?? '-'} · active ${systemStatus?.task_queue?.active_tasks ?? '-'}`, type: componentReady.task_queue ? 'success' : 'info' },
    { time: runtimeTime, msg: lang === 'zh' ? `[浏览器池] ${systemStatus?.browser_pool?.total_browsers ?? '-'} / ${systemStatus?.browser_pool?.max_browsers ?? '-'} 实例` : `[Browser pool] ${systemStatus?.browser_pool?.total_browsers ?? '-'} / ${systemStatus?.browser_pool?.max_browsers ?? '-'} instances`, type: componentReady.browser_pool ? 'success' : 'info' },
    { time: runtimeTime, msg: lang === 'zh' ? `[AI] ${systemStatus?.ai?.mode === 'online' ? `OpenRouter 在线 · ${systemStatus.ai.marketing_model}` : '本地回退模式'}` : `[AI] ${systemStatus?.ai?.mode === 'online' ? `OpenRouter online · ${systemStatus.ai.marketing_model}` : 'local fallback mode'}`, type: systemStatus?.ai?.configured ? 'success' : 'info' },
  ];
  const dashboardAgents = [
    { nameZh: '线索提取队列', nameEn: 'Lead Extraction Queue', status: componentReady.task_queue ? 'active' : 'idle', descZh: `等待 ${systemStatus?.task_queue?.queue_size ?? '-'} · 执行中 ${systemStatus?.task_queue?.active_tasks ?? '-'}`, descEn: `Pending ${systemStatus?.task_queue?.queue_size ?? '-'} · Active ${systemStatus?.task_queue?.active_tasks ?? '-'}`, color: componentReady.task_queue ? 'var(--success)' : 'var(--text-muted)' },
    { nameZh: 'Playwright 浏览器池', nameEn: 'Playwright Browser Pool', status: componentReady.browser_pool ? 'active' : 'idle', descZh: `${systemStatus?.browser_pool?.total_browsers ?? '-'} / ${systemStatus?.browser_pool?.max_browsers ?? '-'} 个实例`, descEn: `${systemStatus?.browser_pool?.total_browsers ?? '-'} / ${systemStatus?.browser_pool?.max_browsers ?? '-'} instances`, color: componentReady.browser_pool ? 'var(--success)' : 'var(--text-muted)' },
    { nameZh: 'LLM 路由核心', nameEn: 'LLM Router', status: systemStatus?.ai?.configured ? 'active' : 'idle', descZh: systemStatus?.ai?.configured ? '已连接 OpenRouter' : '本地回退模式', descEn: systemStatus?.ai?.configured ? 'Connected to OpenRouter' : 'Local fallback mode', color: systemStatus?.ai?.configured ? 'var(--success)' : '#f59e0b' },
  ];

  // Leads Tab Data
  const leadsPlatforms = [
    { value: 'x', labelZh: 'X / Twitter', labelEn: 'X / Twitter', descZh: '从推特话题与用户中挖掘线索', descEn: 'Mine leads from tweets & profiles', color: '#1d9bf0', icon: <Globe size={20} /> },
    { value: 'linkedin', labelZh: 'LinkedIn', labelEn: 'LinkedIn', descZh: '从职业网络圈中定向抓取联系人', descEn: 'Target professional network contacts', color: '#0a66c2', icon: <Users size={20} /> },
    { value: 'shopify', labelZh: 'Shopify', labelEn: 'Shopify', descZh: '扫描 Shopify 独立站获取店主信息', descEn: 'Scan Shopify stores for owner data', color: '#96bf48', icon: <Box size={20} /> },
    { value: 'tiktok', labelZh: 'TikTok', labelEn: 'TikTok', descZh: '从 TikTok 创作者中识别商机', descEn: 'Identify creators & opportunities', color: '#ff0050', icon: <Globe size={20} /> },
    { value: 'facebook', labelZh: 'Facebook', labelEn: 'Facebook', descZh: '从群组与主页中提取潜客', descEn: 'Extract leads from groups & pages', color: '#1877f2', icon: <Users size={20} /> },
  ];
  const leadsGeographies = [
    { value: 'all', labelZh: '全球', labelEn: 'Global' },
    { value: 'us', labelZh: '美国', labelEn: 'United States' },
    { value: 'uk', labelZh: '英国', labelEn: 'United Kingdom' },
    { value: 'ca', labelZh: '加拿大', labelEn: 'Canada' },
    { value: 'au', labelZh: '澳大利亚', labelEn: 'Australia' },
    { value: 'de', labelZh: '德国', labelEn: 'Germany' },
    { value: 'fr', labelZh: '法国', labelEn: 'France' },
    { value: 'jp', labelZh: '日本', labelEn: 'Japan' },
    { value: 'sg', labelZh: '新加坡', labelEn: 'Singapore' },
  ];
  const leadsFollowerRanges = [
    { value: '0-1k', labelZh: '0 - 1K', labelEn: '0 - 1K' },
    { value: '1k-10k', labelZh: '1K - 10K', labelEn: '1K - 10K' },
    { value: '10k-50k', labelZh: '10K - 50K', labelEn: '10K - 50K' },
    { value: '50k-100k', labelZh: '50K - 100K', labelEn: '50K - 100K' },
    { value: '100k+', labelZh: '100K+', labelEn: '100K+' },
  ];
  const leadsContentTypes = [
    { value: 'all', labelZh: '全部', labelEn: 'All' },
    { value: 'influencer', labelZh: '影响者', labelEn: 'Influencers' },
    { value: 'business', labelZh: '商业账号', labelEn: 'Business' },
    { value: 'creator', labelZh: '创作者', labelEn: 'Creators' },
    { value: 'reseller', labelZh: '经销商', labelEn: 'Resellers' },
  ];

  // Marketing Tab Data
  const marketingActions = [
    { type: 'email', icon: <Bot size={24} />, color: 'var(--primary)', glow: 'rgba(99,102,241,0.3)', nameZh: '生成个性化开发信', nameEn: 'Generate Cold Email', descZh: '基于客户线索深度定制一封高质量业务开发邮件', descEn: 'Craft a high-quality cold email from lead data', tagZh: '邮件', tagEn: 'Email' },
    { type: 'classify', icon: <Search size={24} />, color: 'var(--accent)', glow: 'rgba(249,115,22,0.3)', nameZh: '批量潜在客户分类', nameEn: 'Batch Lead Scoring', descZh: '使用 AI 对线索意向度评分并分类归档', descEn: 'Score and categorize leads by intent level', tagZh: '评分', tagEn: 'Scoring' },
    { type: 'social', icon: <Sparkles size={24} />, color: 'var(--success)', glow: 'rgba(16,185,129,0.3)', nameZh: 'AI 社交媒体跟进', nameEn: 'AI Social Follow-up', descZh: '生成 Twitter/LinkedIn 高互动跟进私信模板', descEn: 'Generate high-engagement DM templates', tagZh: '社交', tagEn: 'Social' },
    { type: 'pipeline', icon: <Bot size={24} />, color: '#8b5cf6', glow: 'rgba(139,92,246,0.3)', nameZh: '全自动营销管道', nameEn: 'Full Marketing Pipeline', descZh: 'Research Agent + Chat Agent：深度分析线索，自动生成多渠道营销消息', descEn: 'Research Agent + Chat Agent: analyze leads, generate multi-channel messages', tagZh: '全自动化', tagEn: 'Pipeline' },
  ];
  const marketingStatusStyle = { done: { bg: 'rgba(16,185,129,0.15)', color: 'var(--success)', border: 'rgba(16,185,129,0.35)' }, running: { bg: 'rgba(59,130,246,0.15)', color: '#60a5fa', border: 'rgba(59,130,246,0.35)' }, queued: { bg: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)', border: 'rgba(255,255,255,0.1)' } };

  // Skills Tab Data
  const skillsAllSkills = [
    { id: 's1', nameZh: '文案多语言翻译', nameEn: 'Multi-lang Translate', descZh: '一键调用 LLM 技能，将营销文案翻译至多国语言。', descEn: 'Translate marketing copy into multiple languages instantly.', color: 'var(--success)', icon: 'Bot', tag: 'NLP' },
    { id: 's2', nameZh: '深度竞品分析', nameEn: 'Deep Competitor Analysis', descZh: '根据线索自动生成竞品画像与市场趋势结构化研报。', descEn: 'Auto-generate competitor profiles and market trend reports from leads.', color: '#3b82f6', icon: 'Search', tag: 'Research' },
    { id: 's3', nameZh: '邮件主题行优化', nameEn: 'Subject Line Optimizer', descZh: 'AI 生成 10 条高打开率的邮件主题行，适配不同行业场景。', descEn: 'Generate 10 high-open-rate email subject lines tailored to your niche.', color: 'var(--accent)', icon: 'Send', tag: 'Email' },
    { id: 's4', nameZh: '领英触达话术生成', nameEn: 'LinkedIn Outreach Script', descZh: '为指定目标潜客生成领英私信初触脚本，针对性强。', descEn: 'Draft personalized LinkedIn DM scripts for target leads.', color: '#8b5cf6', icon: 'Bot', tag: 'Social' },
    { id: 's5', nameZh: 'A/B 测试变体生成', nameEn: 'A/B Variant Generator', descZh: '为现有营销文案生成多个 A/B 测试版本，助力转化率实验。', descEn: 'Generate multiple A/B test variants of any marketing copy.', color: 'var(--primary)', icon: 'Sparkles', tag: 'CRO' },
    { id: 's6', nameZh: '线索数据清洗', nameEn: 'Lead Data Scrubber', descZh: '自动识别并去除重复、无效或低质量线索条目。', descEn: 'Auto-detect and remove duplicate or low-quality lead entries.', color: '#f59e0b', icon: 'Activity', tag: 'Data' },
  ];
  const skillsIconMap = { Bot: <Bot size={20} />, Search: <Search size={20} />, Send: <Send size={20} />, Sparkles: <Sparkles size={20} />, Activity: <Activity size={20} /> };

  // Analytics State (from backend)
  const [analyticsData, setAnalyticsData] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState('');

  // Fetch analytics data
  const fetchAnalytics = useCallback(async () => {
    setAnalyticsLoading(true);
    setAnalyticsError('');
    try {
      const token = localStorage.getItem('token');
      if (!isTokenValid(token)) {
        if (token) localStorage.removeItem('token');
        setIsLoggedIn(false);
        setUser(null);
        setAnalyticsError(lang === 'zh' ? '登录已过期，请重新登录' : 'Session expired, please log in again');
        return;
      }
      const response = await fetch(`${API_BASE_URL}/api/analytics/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.status === 401) {
        localStorage.removeItem('token');
        setIsLoggedIn(false);
        setUser(null);
        setAnalyticsError(lang === 'zh' ? '登录已过期，请重新登录' : 'Session expired, please log in again');
        return;
      }
      const data = await response.json();
      if (data.success === false) {
        setAnalyticsError(data.error || 'Failed to load analytics');
      } else {
        setAnalyticsData(data);
      }
    } catch {
      setAnalyticsError(lang === 'zh' ? '网络错误' : 'Network error');
    } finally {
      setAnalyticsLoading(false);
    }
  }, [lang]);

  const fetchSystemStatus = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!isTokenValid(token)) return;
    setSystemStatusLoading(true);
    setSystemStatusError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/system/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || data.detail || 'Failed to load runtime status');
      setSystemStatus(data);
    } catch (err) {
      setSystemStatusError(err.message || (lang === 'zh' ? '无法读取运行状态' : 'Unable to load runtime status'));
    } finally {
      setSystemStatusLoading(false);
    }
  }, [lang]);

  const fetchMarketingCampaigns = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!isTokenValid(token)) return;
    setCampaignsLoading(true);
    setCampaignsError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/outreach/campaigns?limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || data.detail || 'Failed to load campaigns');
      setMarketingCampaigns(data.campaigns || []);
    } catch (err) {
      setCampaignsError(err.message || (lang === 'zh' ? '无法读取营销活动' : 'Unable to load campaigns'));
    } finally {
      setCampaignsLoading(false);
    }
  }, [lang]);

  // Check auth status on mount — client-side JWT expiry check (no network request)
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (isTokenValid(token)) {
      const payload = parseJwt(token);
      setIsLoggedIn(true);
      if (payload?.email) setUser({ email: payload.email });
    } else {
      if (token) localStorage.removeItem('token');
      setIsLoggedIn(false);
      setUser(null);
    }
    setAuthLoading(false);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `username=${encodeURIComponent(loginEmail)}&password=${encodeURIComponent(loginPassword)}`
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Login failed');
      }
      localStorage.setItem('token', data.access_token);
      setIsLoggedIn(true);
      setUser({ email: loginEmail });
      setLoginEmail('');
      setLoginPassword('');
    } catch (err) {
      setLoginError(err.message || (lang === 'zh' ? '登录失败' : 'Login failed'));
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoginError('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword, name: registerName || loginEmail.split('@')[0] })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || data.detail || 'Registration failed');
      }
      // Auto login after register
      const loginRes = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `username=${encodeURIComponent(loginEmail)}&password=${encodeURIComponent(loginPassword)}`
      });
      const loginData = await loginRes.json();
      if (!loginRes.ok) {
        throw new Error(loginData.error || 'Registration succeeded but login failed');
      }
      localStorage.setItem('token', loginData.access_token);
      setIsLoggedIn(true);
      setUser({ email: loginEmail });
      setLoginEmail('');
      setLoginPassword('');
      setRegisterName('');
      setIsRegisterMode(false);
    } catch (err) {
      setLoginError(err.message || (lang === 'zh' ? '注册失败' : 'Registration failed'));
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsLoggedIn(false);
    setUser(null);
    setLeads([]);
    setAnalyticsData(null);
    setSystemStatus(null);
    setMarketingCampaigns([]);
    setLeadDetails(null);
  };

  const fetchLeads = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!isTokenValid(token)) return;
    setLeadsLoading(true);
    try {
      const params = new URLSearchParams({ page_size: '100' });
      if (leadsSearch.trim()) params.set('search', leadsSearch.trim());
      if (leadStatusFilter) params.set('status', leadStatusFilter);
      const response = await fetch(`${API_BASE_URL}/api/leads/?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to load leads');
      setLeads(data.leads || []);
      setLeadTotal(data.total || 0);
    } catch (err) {
      setStatusMsg(`[Error] ${err.message || 'Failed to load leads'}`);
    } finally {
      setLeadsLoading(false);
    }
  }, [leadStatusFilter, leadsSearch]);

  const fetchLeadDetails = async (leadId) => {
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${API_BASE_URL}/api/leads/${leadId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to load lead details');
      setLeadDetails(data);
    } catch (err) {
      setStatusMsg(`[Error] ${err.message || 'Failed to load lead details'}`);
    }
  };

  const updateLeadStatus = async (leadId, status) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/api/leads/${leadId}`, {
      method: 'PATCH',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    const data = await response.json();
    if (!response.ok) {
      setStatusMsg(`[Error] ${data.error || 'Failed to update lead'}`);
      return;
    }
    setLeads(prev => prev.map(lead => lead.id === leadId ? data : lead));
    if (leadDetails?.id === leadId) setLeadDetails(prev => ({ ...prev, status: data.status }));
  };

  const deleteLead = async (leadId) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/api/leads/${leadId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!response.ok) {
      const data = await response.json();
      setStatusMsg(`[Error] ${data.error || 'Failed to delete lead'}`);
      return;
    }
    setLeadDetails(prev => prev?.id === leadId ? null : prev);
    await fetchLeads();
  };

  const updateDraftStatus = async (messageId, status) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/api/outreach/${messageId}`, {
      method: 'PATCH',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    const data = await response.json();
    if (!response.ok) {
      setStatusMsg(`[Error] ${data.error || 'Failed to update draft'}`);
      return;
    }
    setLeadDetails(prev => ({
      ...prev,
      marketing_messages: prev.marketing_messages.map(message => message.id === messageId ? data : message)
    }));
  };

  useEffect(() => {
    if (isLoggedIn) fetchLeads();
  }, [isLoggedIn, fetchLeads]);

  // Dashboard and analytics share the persisted workspace summary.
  useEffect(() => {
    if (isLoggedIn && (activeTab === 'analytics' || activeTab === 'dashboard')) {
      fetchAnalytics();
    }
  }, [activeTab, fetchAnalytics, isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return undefined;
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchSystemStatus, isLoggedIn]);

  useEffect(() => {
    if (isLoggedIn && activeTab === 'marketing') fetchMarketingCampaigns();
  }, [activeTab, fetchMarketingCampaigns, isLoggedIn]);

  const chatEndRef = useRef(null);

  // Auto scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isTyping]);

  // Translate greeting on lang change
  useEffect(() => {
    setChatMessages((prev) => {
      const messages = [...prev];
      if (messages.length > 0 && messages[0].role === 'assistant') {
        const isGreeting = (messages[0].content === i18n.en.chatGreeting || messages[0].content === i18n.zh.chatGreeting);
        if (isGreeting) {
          messages[0].content = t.chatGreeting;
        }
      }
      return messages;
    });
  }, [lang, t.chatGreeting]);

  const handleScrape = async () => {
    if (!keyword.trim()) {
      setStatusMsg(lang === 'zh' ? '[错误] 请输入关键词' : '[Error] Please enter a keyword');
      return;
    }
    setIsScraping(true);
    setStatusMsg(`${t.sysInit}${platform}...`);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setStatusMsg(lang === 'zh' ? '[错误] 请先登录' : '[Error] Please log in first');
        return;
      }
      // Call the actual scraping endpoint using LeadAgent
      const response = await fetch(
        `${API_BASE_URL}/api/agents/test-scraper`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            keyword: keyword,
            platform: platform || 'x',
            geography: selectedGeo,
            follower_range: selectedFollowers,
            content_type: selectedContentType,
            max_results: maxResults
          })
        }
      );

      if (response.status === 401) {
        localStorage.removeItem('token');
        setIsLoggedIn(false);
        setUser(null);
        setStatusMsg(lang === 'zh' ? '[错误] 登录已过期，请重新登录' : '[Error] Session expired, please log in again');
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      if (result.status === 'success' && result.data && result.data.length > 0) {
        let sourceInfo = '';
        if (result.source) {
          if (result.source.includes('+ddg')) sourceInfo = lang === 'zh' ? ' (通过 DuckDuckGo 搜索)' : ' (via DuckDuckGo)';
          else if (result.source.includes('+google')) sourceInfo = lang === 'zh' ? ' (通过 Google 搜索)' : ' (via Google)';
        }
        setStatusMsg(`${t.sysSuccess}${result.leads_found}${t.sysSuccessEnd}"${keyword}".${sourceInfo}`);
        await fetchLeads();
      } else if (result.status === 'error') {
        setStatusMsg(lang === 'zh' ? `[错误] 爬取失败: ${result.message}` : `[Error] Scraping failed: ${result.message}`);
      } else {
        // 真实爬取结果为空
        const reason = platform === 'x' || platform === 'twitter' || platform === 'linkedin' || platform === 'instagram' || platform === 'facebook'
          ? (lang === 'zh'
            ? `${platform} 需要登录才能搜索。请先用 Chrome 浏览器登录 ${platform}，然后重启应用重试。若仍失败，可在 .env 中手动配置 CHROME_USER_DATA_DIR 或 CDP_URL`
            : `${platform} requires login. Log in to ${platform} in Chrome first, then restart the app. If it still fails, set CHROME_USER_DATA_DIR or CDP_URL in .env`)
          : (lang === 'zh' ? `未找到匹配「${keyword}」的线索` : `No leads found for "${keyword}"`);
        setStatusMsg(`[!] ${reason}`);
      }
    } catch (err) {
      console.error(err);
      setStatusMsg(t.sysErrorNet);
    } finally {
      setIsScraping(false);
    }
  };

  const handleMarketingAction = async (type) => {
    if (marketingLoading) return;
    setMarketingLoading(true);
    setMarketingResult('');
    const titles = {
      email: lang === 'zh' ? '生成个性化开发信' : 'Generated Cold Email',
      classify: lang === 'zh' ? '批量潜在客户分类' : 'Lead Classification Results',
      social: lang === 'zh' ? 'AI 社交媒体跟进' : 'Social Media Follow-up'
    };
    setMarketingActionTitle(titles[type]);

    try {
      const token = localStorage.getItem('token');
      if (!isTokenValid(token)) {
        setMarketingResult(lang === 'zh' ? '[错误] 请先登录' : '[Error] Please log in first');
        return;
      }
      if (!leads || leads.length === 0) {
        setMarketingResult(lang === 'zh' ? '[错误] 请先在线索捕获器中采集线索。' : '[Error] Extract leads before running a marketing action.');
        return;
      }
      const response = await fetch(`${API_BASE_URL}/api/agents/marketing-action`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          action: type,
          lead_ids: leads.slice(0, type === 'email' ? 1 : 10).map(lead => lead.id),
          product_context: keyword || '',
          language: lang
        })
      });
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        setMarketingResult(data.content);
      } else {
        setMarketingResult(`[Error] ${data.error || data.message || 'Marketing action failed'}`);
      }
    } catch {
      setMarketingResult(t.sysErrorNet || 'Network Error, please ensure backend is running.');
    } finally {
      setMarketingLoading(false);
    }
  };

  const handlePipelineAction = async () => {
    if (pipelineLoading) return;

    const token = localStorage.getItem('token');
    if (!isTokenValid(token)) {
      setPipelineResult({ error: lang === 'zh' ? '请先登录' : 'Please log in first' });
      return;
    }

    if (!leads || leads.length === 0) {
      setPipelineResult({ error: lang === 'zh' ? '请先在「线索捕获器」中采集线索数据' : 'Please extract leads in the Lead Extractor tab first' });
      return;
    }

    setPipelineLoading(true);
    setPipelineResult(null);
    setPipelineStep('research');

    try {
      const response = await fetch(`${API_BASE_URL}/api/agents/marketing-pipeline`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          lead_ids: leads.slice(0, 20).map(lead => lead.id),
          product_context: keyword || '',
          language: lang === 'zh' ? 'zh' : 'en'
        })
      });

      if (response.status === 401) {
        localStorage.removeItem('token');
        setIsLoggedIn(false);
        setUser(null);
        setPipelineResult({ error: lang === 'zh' ? '登录已过期，请重新登录' : 'Session expired, please log in again' });
        return;
      }

      setPipelineStep('chat');
      const data = await response.json();

      if (data.status === 'success') {
        setPipelineResult(data);
        await fetchMarketingCampaigns();
      } else {
        setPipelineResult({ error: data.error || data.message || 'Pipeline failed' });
      }
    } catch {
      setPipelineResult({ error: lang === 'zh' ? '网络错误，请确保后端正在运行' : 'Network error. Please ensure the backend is running.' });
    } finally {
      setPipelineLoading(false);
      setPipelineStep('');
    }
  };

  const handleRunSkill = async (skillId) => {
    if (skillRunning) return;

    const token = localStorage.getItem('token');
    if (!isTokenValid(token)) {
      setSkillResult({ skill_id: skillId, error: t.skillLoginRequired });
      return;
    }

    if (!skillInput.trim()) {
      setSkillResult({ skill_id: skillId, error: t.skillInputRequired });
      return;
    }

    setSkillRunning(skillId);
    setSkillResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/agents/execute-skill`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          skill_id: skillId,
          input_text: skillInput,
          language: lang === 'zh' ? 'zh' : 'en'
        })
      });

      if (response.status === 401) {
        localStorage.removeItem('token');
        setIsLoggedIn(false);
        setUser(null);
        setSkillResult({ skill_id: skillId, error: t.skillLoginRequired });
        return;
      }

      const data = await response.json();
      if (data.status === 'success') {
        setSkillResult({ skill_id: skillId, result: data.result });
      } else {
        setSkillResult({ skill_id: skillId, error: data.detail || 'Skill execution failed' });
      }
    } catch {
      setSkillResult({ skill_id: skillId, error: lang === 'zh' ? '网络错误' : 'Network error' });
    } finally {
      setSkillRunning(null);
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || isTyping) return;
    
    const userMsg = { role: 'user', content: chatInput.trim() };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setIsTyping(true);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setChatMessages(prev => [...prev, { role: 'assistant', content: lang === 'zh' ? '[错误] 请先登录' : '[Error] Please log in first' }]);
        return;
      }
      const response = await fetch(`${API_BASE_URL}/api/agents/test-llm`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: userMsg.content, language: lang })
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      } else {
        setChatMessages(prev => [...prev, { role: 'assistant', content: `[Error] ${data.message}` }]);
      }
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: t.sysError }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleTogglePlugin = (id) => {
    setPlugins(prev => prev.map(p => p.id === id ? { ...p, isActive: !p.isActive } : p));
  };

  const renderPluginIcon = (iconName, color) => {
    switch (iconName) {
      case 'Box': return <Box size={20} color={color} />;
      case 'Bot': return <Bot size={20} color={color} />;
      case 'Search': return <Search size={20} color={color} />;
      default: return <Blocks size={20} color={color} />;
    }
  };

  const filteredPlugins = plugins.filter(p => 
    p.name.toLowerCase().includes(pluginSearchQuery.toLowerCase()) || 
    p.descEn.toLowerCase().includes(pluginSearchQuery.toLowerCase()) ||
    p.descZh.toLowerCase().includes(pluginSearchQuery.toLowerCase())
  );

  const handleInstallPlugin = (plugin) => {
    setPlugins(prev => [...prev, { ...plugin, isActive: true }]);
    setMarketPlugins(prev => prev.filter(p => p.id !== plugin.id));
  };

  if (authLoading) {
    return (
      <div className="dashboard-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          <Loader2 size={48} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 1rem' }} />
          <p>{lang === 'zh' ? '加载中...' : 'Loading...'}</p>
        </div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="dashboard-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--bg-primary)' }}>
        <div style={{
          background: 'rgba(0,0,0,0.4)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '12px',
          padding: '2.5rem',
          width: '100%',
          maxWidth: '400px',
          textAlign: 'center'
        }}>
          <h2 style={{ color: '#fff', marginBottom: '1.5rem', fontSize: '1.5rem' }}>{t.brand}</h2>
          <form onSubmit={isRegisterMode ? handleRegister : handleLogin}>
            {isRegisterMode && (
              <input
                type="text"
                placeholder={lang === 'zh' ? '姓名' : 'Name'}
                value={registerName}
                onChange={e => setRegisterName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  marginBottom: '1rem',
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '1rem',
                  boxSizing: 'border-box'
                }}
              />
            )}
            <input
              type="email"
              placeholder="Email"
              value={loginEmail}
              onChange={e => setLoginEmail(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                marginBottom: '1rem',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '1rem',
                boxSizing: 'border-box'
              }}
            />
            <input
              type="password"
              placeholder={lang === 'zh' ? '密码' : 'Password'}
              value={loginPassword}
              onChange={e => setLoginPassword(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '0.75rem 1rem',
                marginBottom: '1rem',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '1rem',
                boxSizing: 'border-box'
              }}
            />
            {loginError && (
              <div style={{ color: '#ef4444', marginBottom: '1rem', fontSize: '0.9rem' }}>{loginError}</div>
            )}
            <button type="submit" className="btn" style={{ width: '100%', marginBottom: '1rem' }}>
              {isRegisterMode ? (lang === 'zh' ? '注册' : 'Register') : (lang === 'zh' ? '登录' : 'Login')}
            </button>
          </form>
          <button
            onClick={() => { setIsRegisterMode(!isRegisterMode); setLoginError(''); }}
            style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.9rem' }}
          >
            {isRegisterMode ? (lang === 'zh' ? '已有账号？登录' : 'Have an account? Login') : (lang === 'zh' ? '没有账号？注册' : 'No account? Register')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <nav className="sidebar">
        <div className="brand">
          <Box className="brand-icon" size={32} />
          <span>{t.brand}</span>
        </div>
        
        <div className={`nav-link ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
          <LayoutDashboard size={20} />
          {t.tabDashboard}
        </div>
        <div className={`nav-link ${activeTab === 'leads' ? 'active' : ''}`} onClick={() => setActiveTab('leads')}>
          <Users size={20} />
          {t.tabLeads}
        </div>
        <div className={`nav-link ${activeTab === 'marketing' ? 'active' : ''}`} onClick={() => setActiveTab('marketing')}>
          <Send size={20} />
          {t.tabMarketing}
        </div>
        <div className={`nav-link ${activeTab === 'analytics' ? 'active' : ''}`} onClick={() => setActiveTab('analytics')}>
          <BarChart3 size={20} />
          {t.tabAnalytics}
        </div>
        <div className={`nav-link ${activeTab === 'plugins' ? 'active' : ''}`} onClick={() => setActiveTab('plugins')}>
          <Blocks size={20} />
          {t.tabPlugins}
        </div>
        <div className={`nav-link ${activeTab === 'skills' ? 'active' : ''}`} onClick={() => setActiveTab('skills')}>
          <Sparkles size={20} />
          {t.tabSkills}
        </div>
        <div className={`nav-link ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')} style={{ marginTop: 'auto' }}>
          <Settings size={20} />
          {t.tabSettings}
        </div>
      </nav>

      {/* Main Container */}
      <main className="main-content">
        <header className="header">
          <h1 className="page-title">
            {activeTab === 'dashboard' ? t.headerDashboard : 
             activeTab === 'leads' ? t.headerLeads :
             activeTab === 'marketing' ? t.tabMarketing :
             activeTab === 'plugins' ? t.tabPlugins :
             activeTab === 'analytics' ? t.tabAnalytics :
             activeTab === 'skills' ? t.tabSkills : t.tabSettings}
          </h1>
          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
            {isLoggedIn ? (
              <button
                onClick={handleLogout}
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: 'var(--text-main)',
                  padding: '0.4rem 0.8rem',
                  borderRadius: '2rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  fontFamily: 'inherit',
                  fontWeight: 600,
                  transition: 'all 0.3s ease',
                  fontSize: '0.9rem'
                }}
              >
                {lang === 'zh' ? '退出' : 'Logout'}
              </button>
            ) : (
              <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                {lang === 'zh' ? '未登录' : 'Not logged in'}
              </span>
            )}
            <button
              onClick={() => setLang(l => l === 'zh' ? 'en' : 'zh')}
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'var(--text-main)',
                padding: '0.4rem 0.8rem',
                borderRadius: '2rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                fontFamily: 'inherit',
                fontWeight: 600,
                transition: 'all 0.3s ease',
                fontSize: '0.9rem'
              }}
            >
              <Globe size={16} />
              {lang === 'zh' ? 'English' : '中文'}
            </button>
            <div className="status-indicator" title={systemStatusError || systemStatus?.status || ''}>
              <span className="pulse" style={{ background: systemStatus?.status === 'healthy' ? 'var(--success)' : '#f59e0b' }}></span>
              {systemStatus?.status === 'healthy'
                ? (lang === 'zh' ? '服务正常' : 'Server Healthy')
                : (lang === 'zh' ? '状态检查中' : 'Checking Status')}
            </div>
          </div>
        </header>

        <div className="content-body">
          {activeTab === 'dashboard' && (
              <>
                {/* ── Row 1: Stat Cards ── */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                  {[
                    { labelZh: '已提取线索', labelEn: 'Leads Extracted', value: analyticsData?.dashboard?.total_leads ?? leadTotal, sub: lang === 'zh' ? `近 7 天 +${analyticsData?.dashboard?.new_leads_this_week ?? 0}` : `+${analyticsData?.dashboard?.new_leads_this_week ?? 0} in 7 days`, icon: <Users size={20} />, color: 'var(--primary)', glow: 'rgba(99,102,241,0.3)' },
                    { labelZh: '系统健康度', labelEn: 'System Health', value: systemStatus?.status === 'healthy' ? (lang === 'zh' ? '正常' : 'Healthy') : (lang === 'zh' ? '检查中' : 'Checking'), sub: systemStatus?.environment || 'development', icon: <Activity size={20} />, color: systemStatus?.status === 'healthy' ? 'var(--success)' : '#f59e0b', glow: 'rgba(16,185,129,0.3)' },
                    { labelZh: '活动任务', labelEn: 'Active Tasks', value: analyticsData?.dashboard?.active_tasks ?? systemStatus?.task_queue?.active_tasks ?? 0, sub: lang === 'zh' ? `队列等待 ${systemStatus?.task_queue?.queue_size ?? 0}` : `${systemStatus?.task_queue?.queue_size ?? 0} queued`, icon: <Bot size={20} />, color: 'var(--accent)', glow: 'rgba(249,115,22,0.3)' },
                    { labelZh: 'AI 生成模式', labelEn: 'AI Generation', value: systemStatus?.ai?.configured ? 'Online' : 'Local', sub: systemStatus?.ai?.configured ? 'OpenRouter' : (lang === 'zh' ? '本地回退' : 'fallback'), icon: <Sparkles size={20} />, color: '#8b5cf6', glow: 'rgba(139,92,246,0.3)' },
                  ].map((card, i) => (
                    <div key={i} className="stat-card" style={{ padding: '1.25rem 1.5rem', background: 'rgba(0,0,0,0.25)', position: 'relative', overflow: 'hidden' }}>
                      <div style={{ position: 'absolute', top: 0, right: 0, width: 80, height: 80, borderRadius: '50%', background: card.glow, filter: 'blur(28px)', transform: 'translate(20px,-20px)' }} />
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: 500, letterSpacing: '0.03em' }}>{lang === 'zh' ? card.labelZh : card.labelEn}</span>
                        <span style={{ color: card.color, opacity: 0.85 }}>{card.icon}</span>
                      </div>
                      <div style={{ fontSize: '2rem', fontWeight: 700, color: '#fff', lineHeight: 1.1, letterSpacing: '-0.02em' }}>{card.value}</div>
                      <div style={{ fontSize: '0.78rem', color: card.color, marginTop: '0.4rem', opacity: 0.8 }}>{card.sub}</div>
                    </div>
                  ))}
                </div>

                {/* ── Row 2: Quick Actions + System Log ── */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: '1rem', marginTop: '1rem' }}>
                  {/* Quick Actions */}
                  <div className="glass-panel" style={{ padding: '1.5rem' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Terminal size={17} color="var(--primary)" />
                      {lang === 'zh' ? '快捷操作' : 'Quick Actions'}
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                      {dashboardQuickActions.map((a, i) => (
                        <button key={i} onClick={() => setActiveTab(a.tab)} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 1rem', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '0.5rem', cursor: 'pointer', color: '#fff', fontFamily: 'inherit', fontSize: '0.9rem', fontWeight: 500, transition: 'all 0.2s', textAlign: 'left' }}
                          onMouseOver={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.borderColor = a.color + '55'; }}
                          onMouseOut={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'; }}
                        >
                          <span style={{ color: a.color, flexShrink: 0 }}>{a.icon}</span>
                          {lang === 'zh' ? a.labelZh : a.labelEn}
                          <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.8rem' }}>→</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* System Activity Log */}
                  <div className="glass-panel" style={{ padding: '1.5rem' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Activity size={17} color="var(--accent)" />
                      {lang === 'zh' ? '系统活动流' : 'System Activity Feed'}
                      <span style={{ marginLeft: 'auto', width: 8, height: 8, borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 8px var(--success)', display: 'inline-block' }} />
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                      {dashboardSystemLogs.map((log, i) => (
                        <div key={i} style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start', padding: '0.55rem 0.75rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', borderLeft: `3px solid ${log.type === 'success' ? 'var(--success)' : 'var(--primary)'}` }}>
                          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontFamily: 'monospace', flexShrink: 0, paddingTop: '0.05rem' }}>{log.time}</span>
                          <span style={{ fontSize: '0.83rem', color: log.type === 'success' ? '#a7f3d0' : 'var(--text-muted)', fontFamily: 'monospace', lineHeight: 1.4 }}>{log.msg}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* ── Row 3: Agent Status Bar ── */}
                <div className="glass-panel" style={{ marginTop: '1rem', padding: '1.25rem 1.5rem' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Bot size={17} color="#8b5cf6" />
                    {lang === 'zh' ? 'Agent 运行状态' : 'Agent Status'}
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                    {dashboardAgents.map((agent, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.9rem 1.1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div style={{ width: 10, height: 10, borderRadius: '50%', background: agent.color, boxShadow: `0 0 8px ${agent.color}`, flexShrink: 0 }} />
                        <div>
                          <div style={{ color: '#fff', fontWeight: 600, fontSize: '0.9rem' }}>{lang === 'zh' ? agent.nameZh : agent.nameEn}</div>
                          <div style={{ color: agent.color, fontSize: '0.78rem', marginTop: '0.15rem' }}>{lang === 'zh' ? agent.descZh : agent.descEn}</div>
                        </div>
                        <span style={{ marginLeft: 'auto', fontSize: '0.72rem', padding: '0.15rem 0.55rem', borderRadius: '1rem', background: agent.status === 'active' ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.06)', color: agent.status === 'active' ? 'var(--success)' : 'var(--text-muted)', border: `1px solid ${agent.status === 'active' ? 'rgba(16,185,129,0.3)' : 'transparent'}`, fontWeight: 600 }}>
                          {agent.status === 'active' ? (lang === 'zh' ? '运行中' : 'Active') : (lang === 'zh' ? '待机' : 'Idle')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

          {activeTab === 'leads' && (
            <>
              {/* ── Top Control Panel ── */}
              <div className="glass-panel" style={{ padding: '1.5rem' }}>
                <h2 className="panel-title" style={{ marginBottom: '1.25rem' }}>
                  <Search size={20} className="brand-icon" />
                  {lang === 'zh' ? '目标捕获参数' : 'Target Acquisition Parameters'}
                </h2>

                {/* Platform Cards */}
                <div style={{ marginBottom: '1rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {lang === 'zh' ? '▼ 目标平台' : '▼ Target Platform'}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.5rem' }}>
                    {leadsPlatforms.map(p => (
                      <div key={p.value} onClick={() => setPlatform(p.value)} style={{ padding: '0.7rem 0.6rem', borderRadius: '0.5rem', border: `2px solid ${platform === p.value ? p.color : 'rgba(255,255,255,0.06)'}`, background: platform === p.value ? `${p.color}18` : 'rgba(255,255,255,0.02)', cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ color: platform === p.value ? p.color : 'var(--text-muted)', flexShrink: 0 }}>{p.icon}</span>
                        <div style={{ overflow: 'hidden' }}>
                          <div style={{ color: platform === p.value ? '#fff' : 'var(--text-muted)', fontWeight: 600, fontSize: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{lang === 'zh' ? p.labelZh : p.labelEn}</div>
                        </div>
                        {platform === p.value && <span style={{ width: 6, height: 6, borderRadius: '50%', background: p.color, boxShadow: `0 0 6px ${p.color}`, flexShrink: 0 }} />}
                      </div>
                    ))}
                  </div>
                </div>
                  {/* Keyword Input */}
                  <div style={{ marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {lang === 'zh' ? '▼ 关键词 / Niche Keyword' : '▼ Keyword / Niche'}
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                      <div style={{ flex: 1, position: 'relative' }}>
                        <Search size={16} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
                        <input
                          type="text"
                          className="input-field"
                          placeholder={lang === 'zh' ? '输入垂直领域关键词 (例: fitness equipment)' : 'Enter niche keyword (e.g. fitness equipment)'}
                          value={keyword}
                          onChange={e => setKeyword(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter' && !isScraping) handleScrape(); }}
                          style={{ width: '100%', paddingLeft: '2.5rem', boxSizing: 'border-box' }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Extended Parameters Row */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
                    {/* Geographic Filter */}
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {lang === 'zh' ? '▼ 目标地区' : '▼ Geography'}
                      </div>
                      <select
                        value={selectedGeo}
                        onChange={e => setSelectedGeo(e.target.value)}
                        className="input-field"
                        style={{ width: '100%', padding: '0.6rem 0.8rem', fontSize: '0.82rem' }}
                      >
                        {leadsGeographies.map(g => (
                          <option key={g.value} value={g.value}>{lang === 'zh' ? g.labelZh : g.labelEn}</option>
                        ))}
                      </select>
                    </div>

                    {/* Follower Range */}
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {lang === 'zh' ? '▼ 粉丝规模' : '▼ Followers'}
                      </div>
                      <select
                        value={selectedFollowers}
                        onChange={e => setSelectedFollowers(e.target.value)}
                        className="input-field"
                        style={{ width: '100%', padding: '0.6rem 0.8rem', fontSize: '0.82rem' }}
                      >
                        {leadsFollowerRanges.map(f => (
                          <option key={f.value} value={f.value}>{lang === 'zh' ? f.labelZh : f.labelEn}</option>
                        ))}
                      </select>
                    </div>

                    {/* Content Type */}
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {lang === 'zh' ? '▼ 账号类型' : '▼ Account Type'}
                      </div>
                      <select
                        value={selectedContentType}
                        onChange={e => setSelectedContentType(e.target.value)}
                        className="input-field"
                        style={{ width: '100%', padding: '0.6rem 0.8rem', fontSize: '0.82rem' }}
                      >
                        {leadsContentTypes.map(c => (
                          <option key={c.value} value={c.value}>{lang === 'zh' ? c.labelZh : c.labelEn}</option>
                        ))}
                      </select>
                    </div>

                    {/* Max Results */}
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {lang === 'zh' ? '▼ 最大数量' : '▼ Max Results'}
                      </div>
                      <select
                        value={maxResults}
                        onChange={e => setMaxResults(parseInt(e.target.value))}
                        className="input-field"
                        style={{ width: '100%', padding: '0.6rem 0.8rem', fontSize: '0.82rem' }}
                      >
                        <option value={10}>10</option>
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                        <option value={200}>200</option>
                      </select>
                    </div>
                  </div>

                  {/* Deploy Button */}
                  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    <button className="btn" onClick={handleScrape} disabled={isScraping} style={{ minWidth: '180px', padding: '0 1.5rem', gap: '0.5rem', background: isScraping ? 'rgba(99,102,241,0.2)' : 'var(--primary)', color: '#fff', fontWeight: 600 }}>
                      {isScraping ? <Loader2 size={16} className="loading-spinner" /> : <Search size={16} />}
                      {isScraping ? (lang === 'zh' ? '挖掘中...' : 'Mining...') : (lang === 'zh' ? '部署提取器' : 'Deploy Extractor')}
                    </button>

                    {/* Current Params Summary */}
                    {!isScraping && keyword && (
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '0.25rem', background: 'rgba(99,102,241,0.15)', color: 'var(--primary)' }}>
                          {leadsPlatforms.find(p => p.value === platform)?.labelEn || platform}
                        </span>
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '0.25rem', background: 'rgba(16,185,129,0.12)', color: 'var(--success)' }}>
                          &quot;{keyword}&quot;
                        </span>
                        {selectedGeo !== 'all' && (
                          <span style={{ padding: '0.2rem 0.5rem', borderRadius: '0.25rem', background: 'rgba(245,158,11,0.12)', color: '#f59e0b' }}>
                            {leadsGeographies.find(g => g.value === selectedGeo)?.labelEn}
                          </span>
                        )}
                        {selectedFollowers !== 'all' && (
                          <span style={{ padding: '0.2rem 0.5rem', borderRadius: '0.25rem', background: 'rgba(139,92,246,0.12)', color: '#8b5cf6' }}>
                            {selectedFollowers}
                          </span>
                        )}
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '0.25rem', background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
                          max {maxResults}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Status / Progress bar */}
                  {isScraping && (
                    <div style={{ marginTop: '1rem' }}>
                      <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{ height: '100%', background: 'linear-gradient(90deg, var(--primary), #8b5cf6)', borderRadius: 99, animation: 'progressPulse 1.5s ease-in-out infinite', width: '60%' }} />
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--primary)', marginTop: '0.5rem', fontFamily: 'monospace' }}>
                        {lang === 'zh' ? `正在扫描 ${leadsPlatforms.find(p2 => p2.value === platform)?.labelZh || platform} · ${keyword}` : `Scanning ${platform} for "${keyword}"...`}
                      </p>
                    </div>
                  )}

                  {statusMsg && !isScraping && (
                    <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'flex-start', gap: '0.6rem', padding: '0.7rem 1rem', background: statusMsg.includes('[Error]') || statusMsg.includes('[错误]') ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)', borderRadius: '0.5rem', border: `1px solid ${statusMsg.includes('[Error]') || statusMsg.includes('[错误]') ? 'rgba(239,68,68,0.25)' : 'rgba(16,185,129,0.25)'}` }}>
                      <span style={{ color: statusMsg.includes('[Error]') || statusMsg.includes('[错误]') ? '#f87171' : 'var(--success)', flexShrink: 0, marginTop: '0.05rem' }}>
                        <Activity size={14} />
                      </span>
                      <span style={{ fontSize: '0.85rem', color: statusMsg.includes('[Error]') || statusMsg.includes('[错误]') ? '#fca5a5' : '#a7f3d0', fontFamily: 'monospace' }}>{statusMsg}</span>
                    </div>
                  )}
                </div>

                {/* ── Results Panel ── */}
                <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', marginTop: '1rem' }}>
                  {/* Panel header with stats */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                    <h2 className="panel-title" style={{ marginBottom: 0 }}>
                      <Terminal size={20} className="brand-icon" />
                      {lang === 'zh' ? '神经数据流' : 'Neural Data Stream'}
                    </h2>
                    {leads.length > 0 && (
                      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                          {lang === 'zh' ? `共 ${leads.length} 条线索` : `${leads.length} leads found`}
                        </span>
                        <button style={{ padding: '0.3rem 0.8rem', fontSize: '0.8rem', fontWeight: 600, background: 'rgba(16,185,129,0.12)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '0.4rem', cursor: 'pointer', fontFamily: 'inherit' }}
                          onClick={() => setActiveTab('marketing')}>
                          {lang === 'zh' ? '→ 发送至营销引擎' : '→ Send to Marketing'}
                        </button>
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '1rem', alignItems: 'center' }}>
                    <input
                      className="input-field"
                      value={leadsSearch}
                      onChange={e => setLeadsSearch(e.target.value)}
                      placeholder={lang === 'zh' ? '搜索用户名或邮箱' : 'Search username or email'}
                      style={{ flex: 1, padding: '0.55rem 0.8rem' }}
                    />
                    <select className="input-field" value={leadStatusFilter} onChange={e => setLeadStatusFilter(e.target.value)} style={{ padding: '0.55rem 0.8rem' }}>
                      <option value="">{lang === 'zh' ? '全部状态' : 'All statuses'}</option>
                      <option value="new">New</option>
                      <option value="contacted">Contacted</option>
                      <option value="qualified">Qualified</option>
                      <option value="converted">Converted</option>
                      <option value="lost">Lost</option>
                    </select>
                    <button className="btn" onClick={fetchLeads} disabled={leadsLoading} style={{ padding: '0.55rem 0.8rem', gap: '0.35rem' }}>
                      <RefreshCw size={14} className={leadsLoading ? 'loading-spinner' : ''} />
                      {leadTotal}
                    </button>
                  </div>

                  {leads.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', overflowY: 'auto' }}>
                      {leads.map((lead, idx) => {
                        const platformColor = lead.platform === 'x' ? '#1d9bf0' : lead.platform === 'linkedin' ? '#0a66c2' : '#96bf48';
                        return (
                          <div key={lead.id || idx} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.9rem 1.1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)', transition: 'border-color 0.2s' }}
                            onMouseOver={e => e.currentTarget.style.borderColor = 'rgba(99,102,241,0.35)'}
                            onMouseOut={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)'}
                          >
                            {/* Index */}
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace', width: '1.5rem', flexShrink: 0, textAlign: 'center' }}>{'0' + (idx + 1)}</span>
                            {/* Platform badge */}
                            <span style={{ padding: '0.2rem 0.6rem', borderRadius: '0.3rem', fontSize: '0.72rem', fontWeight: 700, background: `${platformColor}20`, color: platformColor, border: `1px solid ${platformColor}40`, flexShrink: 0, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{lead.platform}</span>
                            {/* Username */}
                            <span style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem', minWidth: '8rem', flexShrink: 0 }}>{lead.username}</span>
                            {/* URL */}
                            <a href={lead.profile_url} target="_blank" rel="noreferrer" style={{ color: 'var(--primary)', fontSize: '0.82rem', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                              {lead.profile_url}
                            </a>
                            {/* Tags */}
                            <div style={{ display: 'flex', gap: '0.3rem', flexShrink: 0 }}>
                              {lead.tags?.slice(0, 3).map((tag, ti) => (
                                <span key={ti} style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '0.25rem', background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)', border: '1px solid rgba(255,255,255,0.08)' }}>{tag}</span>
                              ))}
                            </div>
                            <select value={lead.status || 'new'} onChange={e => updateLeadStatus(lead.id, e.target.value)} className="input-field" style={{ padding: '0.3rem 0.45rem', fontSize: '0.72rem' }}>
                              <option value="new">New</option>
                              <option value="contacted">Contacted</option>
                              <option value="qualified">Qualified</option>
                              <option value="converted">Converted</option>
                              <option value="lost">Lost</option>
                            </select>
                            <button title="Details" onClick={() => fetchLeadDetails(lead.id)} style={{ color: 'var(--primary)', background: 'transparent', border: 0, cursor: 'pointer' }}><Eye size={15} /></button>
                            <button title="Delete" onClick={() => deleteLead(lead.id)} style={{ color: '#f87171', background: 'transparent', border: 0, cursor: 'pointer' }}><Trash2 size={15} /></button>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 2rem', color: 'var(--text-muted)' }}>
                      {isScraping ? (
                        <>
                          <div style={{ width: 48, height: 48, borderRadius: '50%', border: '3px solid rgba(99,102,241,0.3)', borderTopColor: 'var(--primary)', animation: 'spin 1s linear infinite', marginBottom: '1.5rem' }} />
                          <p style={{ fontSize: '0.9rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--primary)' }}>
                            {lang === 'zh' ? '突触连接建立中...' : 'Establishing neural link...'}
                          </p>
                        </>
                      ) : (
                        <>
                          <div style={{ width: 72, height: 72, borderRadius: '50%', background: 'rgba(99,102,241,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1.5rem', border: '1px solid rgba(99,102,241,0.15)' }}>
                            <Search size={32} style={{ opacity: 0.25 }} />
                          </div>
                          <p style={{ fontSize: '0.95rem', fontWeight: 500, marginBottom: '0.5rem', color: '#fff', opacity: 0.4 }}>
                            {lang === 'zh' ? '等待提取任务部署' : 'Awaiting Extraction Deployment'}
                          </p>
                          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', maxWidth: '300px', textAlign: 'center', lineHeight: 1.6 }}>
                            {lang === 'zh' ? '选择目标平台并输入关键词，点击「部署提取器」启动任务。' : 'Select a platform, enter a keyword, then click Deploy Extractor to begin.'}
                          </p>
                        </>
                      )}
                    </div>
                  )}
                </div>

                {leadDetails && (
                  <div className="glass-panel" style={{ marginTop: '1rem', padding: '1rem 1.1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginBottom: '0.75rem' }}>
                      <div>
                        <strong>{leadDetails.username}</strong>
                        <span style={{ marginLeft: '0.6rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                          {leadDetails.platform} · score {leadDetails.quality_score || 0}
                        </span>
                      </div>
                      <button onClick={() => setLeadDetails(null)} style={{ color: 'var(--text-muted)', background: 'transparent', border: 0, cursor: 'pointer' }}><X size={16} /></button>
                    </div>
                    {leadDetails.metadata && Object.keys(leadDetails.metadata).length > 0 && (
                      <pre style={{ color: 'var(--text-muted)', whiteSpace: 'pre-wrap', fontSize: '0.75rem' }}>{JSON.stringify(leadDetails.metadata, null, 2)}</pre>
                    )}
                    <div style={{ display: 'grid', gap: '0.55rem', marginTop: '0.75rem' }}>
                      {(leadDetails.marketing_messages || []).map(message => (
                        <div key={message.id} style={{ padding: '0.75rem', background: 'rgba(0,0,0,0.18)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '0.45rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                            <strong style={{ fontSize: '0.78rem' }}>{message.channel}</strong>
                            <select value={message.status} onChange={e => updateDraftStatus(message.id, e.target.value)} className="input-field" style={{ padding: '0.2rem 0.35rem', fontSize: '0.7rem' }}>
                              <option value="draft">Draft</option>
                              <option value="approved">Approved</option>
                              <option value="sent">Sent</option>
                              <option value="archived">Archived</option>
                            </select>
                          </div>
                          {message.subject && <div style={{ marginTop: '0.35rem', color: '#fff', fontSize: '0.78rem' }}>{message.subject}</div>}
                          <div style={{ marginTop: '0.35rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap', fontSize: '0.76rem' }}>{message.body}</div>
                        </div>
                      ))}
                      {(leadDetails.marketing_messages || []).length === 0 && (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                          {lang === 'zh' ? '暂无营销草稿，请在营销引擎运行 Pipeline。' : 'No outreach drafts yet. Run the Pipeline in Marketing Engine.'}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}


          {activeTab === 'marketing' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* ── Row 1: Two columns ── */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: '1rem' }}>
                {/* Left: Action Cards */}
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <h2 className="panel-title" style={{ marginBottom: '0.5rem' }}>
                    <Send size={18} className="brand-icon" />
                    {lang === 'zh' ? 'AI 营销动作' : 'AI Marketing Actions'}
                  </h2>
                  {marketingActions.map(a => (
                    <button key={a.type} onClick={() => a.type === 'pipeline' ? handlePipelineAction() : handleMarketingAction(a.type)} disabled={marketingLoading || pipelineLoading}
                        style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.1rem', background: (marketingLoading || pipelineLoading) ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.2)', border: `1px solid rgba(255,255,255,0.07)`, borderRadius: '0.6rem', cursor: (marketingLoading || pipelineLoading) ? 'not-allowed': 'pointer', fontFamily: 'inherit', transition: 'all 0.2s', textAlign: 'left', opacity: (marketingLoading || pipelineLoading) ? 0.6 : 1, position: 'relative', overflow: 'hidden' }}
                        onMouseOver={e => { if (!marketingLoading && !pipelineLoading) { e.currentTarget.style.borderColor = a.color + '55'; e.currentTarget.style.background = `${a.glow.replace('0.3', '0.08')}`; }}}
                        onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'; e.currentTarget.style.background = 'rgba(0,0,0,0.2)'; }}
                      >
                        <div style={{ width: 44, height: 44, borderRadius: '0.5rem', background: `${a.glow.replace('0.3','0.15')}`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: a.color, flexShrink: 0 }}>{a.icon}</div>
                        <div style={{ flex: 1 }}>
                          <div style={{ color: '#fff', fontWeight: 600, fontSize: '0.9rem' }}>{lang === 'zh' ? a.nameZh : a.nameEn}</div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.77rem', marginTop: '0.2rem', lineHeight: 1.4 }}>{lang === 'zh' ? a.descZh : a.descEn}</div>
                        </div>
                        <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '1rem', background: `${a.glow.replace('0.3','0.15')}`, color: a.color, fontWeight: 600, flexShrink: 0 }}>{lang === 'zh' ? a.tagZh : a.tagEn}</span>
                      </button>
                    ))}
                  </div>

                  {/* Right: AI Result Output */}
                  <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
                    <h2 className="panel-title" style={{ marginBottom: '1rem' }}>
                      <Bot size={18} className="brand-icon" />
                      {lang === 'zh' ? 'AI 生成结果' : 'AI Output'}
                      {(marketingResult || (pipelineResult && !pipelineResult.error)) && !marketingLoading && !pipelineLoading && (
                        <button onClick={() => {
                          if (pipelineResult && !pipelineResult.error && pipelineResult.results) {
                            const allText = pipelineResult.results.map(r => {
                              const lead = r.lead || {};
                              const research = r.research || {};
                              const msgList = Array.isArray(r.messages) ? r.messages : [];
                              const msgs = {};
                              msgList.forEach(m => { if (m.channel) msgs[m.channel] = m; });
                              let text = `--- ${lead.username || 'Lead'} (${lead.platform}) ---\nTier: ${research.tier || '?'} | Score: ${research.quality_score || '?'}\n`;
                              if (msgs.email) text += `\n[Email]\nSubject: ${msgs.email.subject}\n${msgs.email.body}\n`;
                              if (msgs.linkedin_dm) text += `\n[LinkedIn DM]\n${msgs.linkedin_dm.body}\n`;
                              if (msgs.twitter_dm) text += `\n[Twitter DM]\n${msgs.twitter_dm.body}\n`;
                              return text;
                            }).join('\n\n');
                            navigator.clipboard?.writeText(allText);
                          } else if (marketingResult) {
                            navigator.clipboard?.writeText(marketingResult);
                          }
                        }} style={{ marginLeft: 'auto', fontSize: '0.75rem', padding: '0.2rem 0.6rem', borderRadius: '0.3rem', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>
                          {lang === 'zh' ? '复制' : 'Copy'}
                        </button>
                      )}
                    </h2>

                    {pipelineLoading ? (
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
                        <div style={{ width: 44, height: 44, borderRadius: '50%', border: '3px solid rgba(139,92,246,0.2)', borderTopColor: '#8b5cf6', animation: 'spin 1s linear infinite' }} />
                        <p style={{ color: '#8b5cf6', fontSize: '0.88rem', fontWeight: 500 }}>
                          {pipelineStep === 'research' ? t.pipelineResearch : pipelineStep === 'chat' ? t.pipelineChat : t.pipelineRunning}
                        </p>
                        <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.75rem' }}>
                          <span style={{ color: pipelineStep === 'research' ? '#8b5cf6' : 'var(--text-muted)', fontWeight: pipelineStep === 'research' ? 600 : 400 }}>1. Research</span>
                          <span style={{ color: 'var(--text-muted)' }}>&rarr;</span>
                          <span style={{ color: pipelineStep === 'chat' ? '#8b5cf6' : 'var(--text-muted)', fontWeight: pipelineStep === 'chat' ? 600 : 400 }}>2. Chat</span>
                        </div>
                      </div>
                    ) : pipelineResult ? (
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                        {pipelineResult.error ? (
                          <div style={{ padding: '1rem', background: 'rgba(239,68,68,0.1)', borderRadius: '0.5rem', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5', fontSize: '0.85rem' }}>
                            {pipelineResult.error}
                          </div>
                        ) : (
                          <>
                            {/* Summary bar */}
                            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                              {pipelineResult.summary && (() => {
                                const tiers = pipelineResult.summary.tier_distribution || {};
                                const items = [
                                  { label: t.pipelineHighTier, count: tiers.A || 0, color: '#10b981' },
                                  { label: t.pipelineMidTier, count: tiers.B || 0, color: '#3b82f6' },
                                  { label: t.pipelineLowTier, count: tiers.C || 0, color: '#6b7280' },
                                ];
                                return items.map((it, i) => (
                                  <span key={i} style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderRadius: '1rem', background: `${it.color}22`, color: it.color, border: `1px solid ${it.color}44`, fontWeight: 600 }}>
                                    {it.label}: {it.count}
                                  </span>
                                ));
                              })()}
                              {pipelineResult.summary && (
                                <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderRadius: '1rem', background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)', fontWeight: 500 }}>
                                  {pipelineResult.summary.messages_generated || 0} {t.pipelineMessages}
                                </span>
                              )}
                              {pipelineResult.results && (
                                <button onClick={() => {
                                  const allText = pipelineResult.results.map(r => {
                                    const lead = r.lead || {};
                                    const research = r.research || {};
                                    const msgList = Array.isArray(r.messages) ? r.messages : [];
                                    const msgs = {};
                                    msgList.forEach(m => { if (m.channel) msgs[m.channel] = m; });
                                    let text = `--- ${lead.username || 'Lead'} (${lead.platform}) ---\nTier: ${research.tier || '?'} | Score: ${research.quality_score || '?'}\nIndustry: ${toArray(research.industry).join(', ')}\n`;
                                    if (msgs.email) text += `\n[Email]\nSubject: ${msgs.email.subject}\n${msgs.email.body}\nCTA: ${msgs.email.cta}\n`;
                                    if (msgs.linkedin_dm) text += `\n[LinkedIn DM]\n${msgs.linkedin_dm.body}\n`;
                                    if (msgs.twitter_dm) text += `\n[Twitter DM]\n${msgs.twitter_dm.body}\n`;
                                    return text;
                                  }).join('\n\n');
                                  navigator.clipboard?.writeText(allText);
                                }} style={{ marginLeft: 'auto', fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderRadius: '0.3rem', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>
                                  {t.pipelineCopyAll}
                                </button>
                              )}
                            </div>

                            {/* Lead cards */}
                            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                              {(pipelineResult.results || []).map((r, i) => {
                                const lead = r.lead || {};
                                const research = r.research || {};
                                const msgList = Array.isArray(r.messages) ? r.messages : [];
                                const msgs = {};
                                msgList.forEach(m => { if (m.channel) msgs[m.channel] = m; });
                                const tierColor = research.tier === 'A' ? '#10b981' : research.tier === 'B' ? '#3b82f6' : '#6b7280';
                                const isExpanded = expandedLead === i;

                                return (
                                  <div key={i} style={{ background: 'rgba(0,0,0,0.25)', borderRadius: '0.5rem', border: `1px solid ${isExpanded ? tierColor + '55' : 'rgba(255,255,255,0.06)'}`, transition: 'border-color 0.2s' }}>
                                    <button onClick={() => setExpandedLead(isExpanded ? null : i)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.7rem 0.85rem', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left' }}>
                                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: tierColor, flexShrink: 0 }} />
                                      <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ color: '#fff', fontSize: '0.85rem', fontWeight: 600 }}>{lead.username || 'Unknown'}</div>
                                        <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{lead.platform} &middot; {toArray(research.industry).join(', ') || '-'}</div>
                                      </div>
                                      <span style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem', borderRadius: '1rem', background: `${tierColor}22`, color: tierColor, fontWeight: 600, flexShrink: 0 }}>
                                        {research.tier === 'A' ? t.pipelineHighTier : research.tier === 'B' ? t.pipelineMidTier : t.pipelineLowTier}
                                      </span>
                                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', flexShrink: 0 }}>{t.pipelineScore}: {research.quality_score || '?'}</span>
                                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', transition: 'transform 0.2s', transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', flexShrink: 0 }}>&#9654;</span>
                                    </button>

                                    {isExpanded && (
                                      <div style={{ padding: '0 0.85rem 0.85rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                                        {/* Talking points */}
                                        {toArray(research.talking_points).length > 0 && (
                                          <div style={{ marginTop: '0.6rem' }}>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '0.3rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Talking Points</div>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                                              {toArray(research.talking_points).map((tp, j) => (
                                                <span key={j} style={{ fontSize: '0.72rem', padding: '0.15rem 0.5rem', borderRadius: '0.3rem', background: 'rgba(255,255,255,0.05)', color: '#d1d5db' }}>{tp}</span>
                                              ))}
                                            </div>
                                          </div>
                                        )}

                                        {/* Messages */}
                                        {[
                                          { key: 'email', label: t.pipelineEmail, data: msgs.email },
                                          { key: 'linkedin_dm', label: t.pipelineLinkedIn, data: msgs.linkedin_dm },
                                          { key: 'twitter_dm', label: t.pipelineTwitter, data: msgs.twitter_dm },
                                        ].filter(m => m.data).map(m => (
                                          <div key={m.key} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', padding: '0.65rem 0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                                              <span style={{ fontSize: '0.72rem', color: '#8b5cf6', fontWeight: 600 }}>{m.label}</span>
                                              <button onClick={() => {
                                                const text = m.data.subject ? `Subject: ${m.data.subject}\n\n${m.data.body}\n\nCTA: ${m.data.cta}` : m.data.body;
                                                navigator.clipboard?.writeText(text);
                                              }} style={{ fontSize: '0.68rem', padding: '0.1rem 0.4rem', borderRadius: '0.25rem', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>
                                                {lang === 'zh' ? '复制' : 'Copy'}
                                              </button>
                                            </div>
                                            {m.data.subject && <div style={{ fontSize: '0.8rem', color: '#fff', fontWeight: 500, marginBottom: '0.25rem' }}>{m.data.subject}</div>}
                                            <div className="ai-output-markdown" style={{ fontSize: '0.78rem', color: '#d1d5db', lineHeight: 1.55 }}><ReactMarkdown>{m.data.body}</ReactMarkdown></div>
                                            {m.data.cta && <div style={{ fontSize: '0.72rem', color: 'var(--accent)', marginTop: '0.3rem' }}>CTA: {m.data.cta}</div>}
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </>
                        )}
                      </div>
                    ) : marketingLoading ? (
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
                        <div style={{ width: 44, height: 44, borderRadius: '50%', border: '3px solid rgba(99,102,241,0.2)', borderTopColor: 'var(--primary)', animation: 'spin 1s linear infinite' }} />
                        <p style={{ color: 'var(--primary)', fontSize: '0.88rem', fontWeight: 500 }}>{lang === 'zh' ? 'AI 分析处理中，请稍候...' : 'AI is processing...'}</p>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{marketingActionTitle}</p>
                      </div>
                    ) : marketingResult ? (
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <div style={{ padding: '0.3rem 0.8rem', background: 'rgba(99,102,241,0.15)', borderRadius: '0.4rem', fontSize: '0.78rem', color: 'var(--primary)', fontWeight: 600, marginBottom: '0.85rem', display: 'inline-flex', alignSelf: 'flex-start', border: '1px solid rgba(99,102,241,0.3)' }}>
                          ✦ {marketingActionTitle}
                        </div>
                        <div className="ai-output-markdown" style={{ flex: 1, overflowY: 'auto', fontSize: '0.88rem', color: '#d1d5db', lineHeight: 1.7, padding: '0.25rem 0' }}>
                          <ReactMarkdown>{marketingResult}</ReactMarkdown>
                        </div>
                      </div>
                    ) : (
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', color: 'var(--text-muted)' }}>
                        <div style={{ width: 60, height: 60, borderRadius: '50%', background: 'rgba(99,102,241,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(99,102,241,0.12)' }}>
                          <Sparkles size={26} style={{ opacity: 0.2 }} />
                        </div>
                        <p style={{ fontSize: '0.88rem', textAlign: 'center', lineHeight: 1.6, maxWidth: '220px' }}>
                          {lang === 'zh' ? '点击左侧 AI 动作按钮，生成结果将显示在此处' : 'Click an AI action on the left to generate output here'}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* ── Row 2: Recent Campaigns ── */}
                <div className="glass-panel" style={{ padding: '1.5rem' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Activity size={17} color="var(--primary)" />
                    {lang === 'zh' ? '近期营销活动' : 'Recent Campaigns'}
                    <button onClick={fetchMarketingCampaigns} disabled={campaignsLoading} style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.25rem 0.6rem', borderRadius: '0.35rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-muted)', cursor: campaignsLoading ? 'wait' : 'pointer', fontFamily: 'inherit', fontSize: '0.72rem' }}>
                      <RefreshCw size={13} className={campaignsLoading ? 'loading-spinner' : ''} />
                      {lang === 'zh' ? '刷新' : 'Refresh'}
                    </button>
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {campaignsError && (
                      <div style={{ color: '#f87171', fontSize: '0.82rem', padding: '0.8rem 1rem', background: 'rgba(239,68,68,0.06)', borderRadius: '0.5rem', border: '1px solid rgba(239,68,68,0.18)' }}>{campaignsError}</div>
                    )}
                    {!campaignsLoading && !campaignsError && marketingCampaigns.length === 0 && (
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.84rem', padding: '1.2rem', textAlign: 'center', background: 'rgba(0,0,0,0.16)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                        {lang === 'zh' ? '暂无营销活动。运行“全自动营销管道”后，活动会自动出现在这里。' : 'No campaigns yet. Run the Full Marketing Pipeline to create one.'}
                      </div>
                    )}
                    {marketingCampaigns.map((c) => {
                      const s = marketingStatusStyle[c.status];
                      const stats = lang === 'zh'
                        ? `${c.lead_count} 条线索 · ${c.total_messages} 条消息 · 已审批 ${c.approved_messages} · 已发送 ${c.sent_messages}`
                        : `${c.lead_count} leads · ${c.total_messages} messages · ${c.approved_messages} approved · ${c.sent_messages} sent`;
                      return (
                        <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.85rem 1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ color: '#fff', fontWeight: 500, fontSize: '0.9rem' }}>{c.name}</div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '0.3rem' }}>{stats}</div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: '0.25rem', opacity: 0.7 }}>{new Date(c.created_at).toLocaleString()} · {c.generation_mode}</div>
                          </div>
                          {/* Progress bar */}
                          {c.status !== 'queued' && (
                            <div style={{ width: 80, flexShrink: 0 }}>
                              <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${c.progress}%`, background: c.status === 'done' ? 'var(--success)' : '#60a5fa', borderRadius: 99, transition: 'width 0.5s' }} />
                              </div>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem', textAlign: 'right' }}>{c.progress}%</div>
                            </div>
                          )}
                          <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '0.2rem 0.6rem', borderRadius: '1rem', background: s.bg, color: s.color, border: `1px solid ${s.border}`, flexShrink: 0 }}>
                            {c.status === 'done' ? (lang === 'zh' ? '已完成' : 'Done') : c.status === 'running' ? (lang === 'zh' ? '执行中' : 'Running') : (lang === 'zh' ? '排队中' : 'Queued')}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}



          {activeTab === 'plugins' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* ── Header Row ── */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.6rem', fontWeight: 700, color: '#fff' }}>{filteredPlugins.length}</span>
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>{lang === 'zh' ? '已安装\n插件' : 'Installed\nPlugins'}</span>
                  </div>
                  <div style={{ width: 1, height: 32, background: 'rgba(255,255,255,0.1)' }} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--success)' }}>{filteredPlugins.filter(p => p.isActive).length}</span>
                    <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>{lang === 'zh' ? '已激活' : 'Active'}</span>
                    </div>
                  </div>
                  <div style={{ position: 'relative', width: 280 }}>
                    <Search size={15} style={{ position: 'absolute', left: '0.9rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
                    <input type="text" className="input-field" placeholder={t.pluginSearch} value={pluginSearchQuery} onChange={e => setPluginSearchQuery(e.target.value)} style={{ width: '100%', paddingLeft: '2.4rem', boxSizing: 'border-box' }} />
                  </div>
                </div>

                {/* ── Plugin Cards Grid ── */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem' }}>
                  {filteredPlugins.map(plugin => (
                    <div key={plugin.id} style={{ padding: '1.25rem', background: 'rgba(0,0,0,0.25)', borderRadius: '0.7rem', border: `1px solid ${plugin.isActive ? `${plugin.color}30` : 'rgba(255,255,255,0.06)'}`, opacity: plugin.isActive ? 1 : 0.65, transition: 'all 0.25s', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                      {/* Header */}
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
                        <div style={{ width: 42, height: 42, borderRadius: '0.5rem', background: plugin.isActive ? `${plugin.color}20` : 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          {renderPluginIcon(plugin.icon, plugin.isActive ? plugin.color : 'var(--text-muted)')}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ color: '#fff', fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.2rem' }}>{plugin.name}</div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>v{plugin.version}</div>
                        </div>
                        <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: '1rem', background: plugin.isActive ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.05)', color: plugin.isActive ? 'var(--success)' : 'var(--text-muted)', border: `1px solid ${plugin.isActive ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.08)'}`, flexShrink: 0 }}>
                          {plugin.isActive ? (lang === 'zh' ? '运行中' : 'Active') : (lang === 'zh' ? '已停用' : 'Inactive')}
                        </span>
                      </div>
                      {/* Description */}
                      <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', lineHeight: 1.55, margin: 0, flex: 1 }}>{lang === 'zh' ? plugin.descZh : plugin.descEn}</p>
                      {/* Footer */}
                      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <button onClick={() => handleTogglePlugin(plugin.id)} style={{ padding: '0.35rem 1rem', borderRadius: '0.4rem', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.2s', background: plugin.isActive ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)', color: plugin.isActive ? '#f87171' : 'var(--success)', border: `1px solid ${plugin.isActive ? 'rgba(239,68,68,0.25)' : 'rgba(16,185,129,0.25)'}` }}>
                          {plugin.isActive ? (lang === 'zh' ? '停用插件' : 'Disable') : (lang === 'zh' ? '启用插件' : 'Enable')}
                        </button>
                      </div>
                    </div>
                  ))}

                  {/* Browse Marketplace Card */}
                  <div onClick={() => setIsMarketplaceOpen(true)} style={{ padding: '1.25rem', background: 'transparent', borderRadius: '0.7rem', border: '2px dashed rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.6rem', cursor: 'pointer', transition: 'all 0.2s', minHeight: '160px' }}
                    onMouseOver={e => { e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)'; e.currentTarget.style.background = 'rgba(99,102,241,0.04)'; }}
                    onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'; e.currentTarget.style.background = 'transparent'; }}>
                    <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'rgba(99,102,241,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(99,102,241,0.15)' }}>
                      <Blocks size={22} style={{ color: 'var(--primary)', opacity: 0.7 }} />
                    </div>
                    <span style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text-muted)' }}>{t.pluginBrowse}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', opacity: 0.6 }}>{lang === 'zh' ? '发现更多插件扩展' : 'Discover more extensions'}</span>
                  </div>
                </div>
              </div>
            )}


          {activeTab === 'analytics' && (() => {
            if (analyticsLoading) {
              return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--text-muted)' }}><span>Loading...</span></div>;
            }
            if (analyticsError) {
              return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: '#f87171' }}><span>{analyticsError}</span></div>;
            }
            const dash = analyticsData?.dashboard;
            const tb = analyticsData?.task_breakdown;
            const lp = analyticsData?.leads_by_platform || [];
            const totalLeads = lp.reduce((s, r) => s + r.count, 0) || 1;

            // KPI cards
            const kpis = [
              { labelZh: '总线索', labelEn: 'Total Leads', value: dash?.total_leads ?? 0, color: '#3b82f6', glow: 'rgba(59,130,246,0.25)', icon: <Users size={18} /> },
              { labelZh: '本周新增', labelEn: 'New This Week', value: dash?.new_leads_this_week ?? 0, color: 'var(--success)', glow: 'rgba(16,185,129,0.25)', icon: <TrendingUp size={18} /> },
              { labelZh: '活跃任务', labelEn: 'Active Tasks', value: dash?.active_tasks ?? 0, color: '#8b5cf6', glow: 'rgba(139,92,246,0.25)', icon: <Activity size={18} /> },
              { labelZh: '已完成', labelEn: 'Completed', value: dash?.completed_tasks ?? 0, color: 'var(--accent)', glow: 'rgba(249,115,22,0.25)', icon: <CheckCircle size={18} /> },
            ];

            // Area chart uses recent_activity as mock trend (last 7 items)
            const chartData = (analyticsData?.recent_activity || []).slice(0, 7).map((a, i) => ({
              name: `#${i + 1}`,
              emails: Math.floor(Math.random() * 50) + 10,
              replies: Math.floor(Math.random() * 20) + 5,
            }));

            return (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* ── Row 1: KPI Cards ── */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                  {kpis.map((k, i) => (
                    <div key={i} className="stat-card" style={{ padding: '1.25rem 1.5rem', background: 'rgba(0,0,0,0.25)', position: 'relative', overflow: 'hidden' }}>
                      <div style={{ position: 'absolute', top: 0, right: 0, width: 70, height: 70, borderRadius: '50%', background: k.glow, filter: 'blur(24px)', transform: 'translate(16px,-16px)' }} />
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>{lang === 'zh' ? k.labelZh : k.labelEn}</span>
                        <span style={{ color: k.color, opacity: 0.85 }}>{k.icon}</span>
                      </div>
                      <div style={{ fontSize: '1.9rem', fontWeight: 700, color: '#fff', lineHeight: 1.1 }}>{k.value}</div>
                    </div>
                  ))}
                </div>

                {/* ── Row 2: Chart + Channel Distribution ── */}
                <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: '1rem' }}>
                  {/* Area Chart */}
                  <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Activity size={17} color="var(--primary)" />
                      {lang === 'zh' ? '互动转化周势' : 'Weekly Engagement Trend'}
                      <span style={{ marginLeft: 'auto', display: 'flex', gap: '1rem', fontSize: '0.75rem', fontWeight: 500 }}>
                        <span style={{ color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}><span style={{ width: 10, height: 3, background: 'var(--primary)', display: 'inline-block', borderRadius: 2 }} />{lang === 'zh' ? '触达量' : 'Outreach'}</span>
                        <span style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}><span style={{ width: 10, height: 3, background: 'var(--accent)', display: 'inline-block', borderRadius: 2 }} />{lang === 'zh' ? '回复量' : 'Replies'}</span>
                      </span>
                    </h3>
                    <div style={{ flex: 1, minHeight: 220 }}>
                      <ResponsiveContainer width="100%" height={220}>
                        <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                          <defs>
                            <linearGradient id="gEmails2" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.5} />
                              <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="gReplies2" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.5} />
                              <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                          <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                          <Tooltip contentStyle={{ backgroundColor: '#0d0d0d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '0.82rem' }} itemStyle={{ color: '#fff' }} />
                          <Area type="monotone" dataKey="emails" name={lang === 'zh' ? '触达量' : 'Outreach'} stroke="var(--primary)" strokeWidth={2} fill="url(#gEmails2)" />
                          <Area type="monotone" dataKey="replies" name={lang === 'zh' ? '回复量' : 'Replies'} stroke="var(--accent)" strokeWidth={2} fill="url(#gReplies2)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Channel Distribution */}
                  <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <BarChart3 size={17} color="var(--accent)" />
                      {lang === 'zh' ? '渠道来源分布' : 'Channel Distribution'}
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1, justifyContent: 'center' }}>
                      {lp.length === 0 ? (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>{lang === 'zh' ? '暂无数据' : 'No data yet'}</span>
                      ) : lp.map((c, i) => {
                        const pct = Math.round((c.count / totalLeads) * 100);
                        const colorMap = { instagram: '#e1306c', tiktok: '#ff0050', x: '#1d9bf0', facebook: '#1877f2', youtube: '#ff0000', linkedin: '#0a66c2' };
                        const color = colorMap[c.platform] || '#6366f1';
                        return (
                          <div key={i}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                              <span style={{ fontSize: '0.85rem', color: '#fff', fontWeight: 500, textTransform: 'capitalize' }}>{c.platform}</span>
                              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{c.count} {lang === 'zh' ? '条' : 'leads'} · <span style={{ color, fontWeight: 600 }}>{pct}%</span></span>
                            </div>
                            <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${pct}%`, background: `linear-gradient(90deg, ${color}, ${color}99)`, borderRadius: 99 }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* ── Row 3: Task Status Breakdown ── */}
                <div className="glass-panel" style={{ padding: '1.5rem' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <CheckCircle size={17} color="var(--success)" />
                    {lang === 'zh' ? '任务状态分布' : 'Task Status Breakdown'}
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.75rem' }}>
                    {tb ? [
                      { label: 'Pending', labelZh: '待处理', value: tb.pending, color: '#f59e0b' },
                      { label: 'Running', labelZh: '运行中', value: tb.running, color: '#3b82f6' },
                      { label: 'Completed', labelZh: '已完成', value: tb.completed, color: 'var(--success)' },
                      { label: 'Failed', labelZh: '失败', value: tb.failed, color: '#ef4444' },
                      { label: 'Cancelled', labelZh: '已取消', value: tb.cancelled, color: 'var(--text-muted)' },
                    ].map((s, i) => (
                      <div key={i} style={{ padding: '0.9rem 1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)', textAlign: 'center' }}>
                        <div style={{ fontSize: '1.5rem', fontWeight: 700, color: s.color }}>{s.value}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>{lang === 'zh' ? s.labelZh : s.label}</div>
                      </div>
                    )) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', gridColumn: '1 / -1', textAlign: 'center' }}>{lang === 'zh' ? '暂无数据' : 'No data yet'}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })()}


          {activeTab === 'skills' && (() => {
            const q = skillSearchQuery.toLowerCase();
            const filtered = skillsAllSkills.filter(s =>
              (lang === 'zh' ? s.nameZh : s.nameEn).toLowerCase().includes(q) ||
              (lang === 'zh' ? s.descZh : s.descEn).toLowerCase().includes(q) ||
              s.tag.toLowerCase().includes(q)
            );

            // Helper to parse result for structured display
            const renderSkillResult = (result, skillId) => {
              if (!result) return null;
              if (result.error) {
                return <div style={{ padding: '0.75rem', background: 'rgba(239,68,68,0.1)', borderRadius: '0.4rem', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5', fontSize: '0.85rem' }}>{result.error}</div>;
              }
              const r = result.result;
              if (!r) return null;

              // Raw output fallback with markdown rendering
              if (r.raw_output) {
                return <div className="ai-output-markdown" style={{ fontSize: '0.85rem', color: '#d1d5db', lineHeight: 1.6 }}><ReactMarkdown>{r.raw_output}</ReactMarkdown></div>;
              }

              // s1: Translations
              if (skillId === 's1' && r.translations) {
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {r.translations.map((item, i) => (
                      <div key={i} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 600, marginBottom: '0.25rem', textTransform: 'uppercase' }}>{item.lang || item.language || `Lang ${i+1}`}</div>
                        <div style={{ fontSize: '0.85rem', color: '#d1d5db', lineHeight: 1.5 }}>{item.text || item.translation || item.content || JSON.stringify(item)}</div>
                      </div>
                    ))}
                  </div>
                );
              }

              // s2: Competitor Analysis
              if (skillId === 's2' && r.competitors) {
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {r.competitors.map((c, i) => (
                      <div key={i} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div style={{ fontSize: '0.88rem', color: '#fff', fontWeight: 600, marginBottom: '0.35rem' }}>{c.name || c.competitor || `Competitor ${i+1}`}</div>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                          {(c.strengths || []).map((s, j) => <span key={j} style={{ fontSize: '0.72rem', padding: '0.1rem 0.45rem', borderRadius: '0.3rem', background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.25)' }}>+ {s}</span>)}
                          {(c.weaknesses || []).map((w, j) => <span key={j} style={{ fontSize: '0.72rem', padding: '0.1rem 0.45rem', borderRadius: '0.3rem', background: 'rgba(239,68,68,0.1)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)' }}>- {w}</span>)}
                        </div>
                        {c.opportunities && c.opportunities.length > 0 && (
                          <div style={{ marginTop: '0.3rem', display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                            {c.opportunities.map((o, j) => <span key={j} style={{ fontSize: '0.72rem', padding: '0.1rem 0.45rem', borderRadius: '0.3rem', background: 'rgba(99,102,241,0.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)' }}>{o}</span>)}
                          </div>
                        )}
                      </div>
                    ))}
                    {r.market_trends && r.market_trends.length > 0 && (
                      <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div style={{ fontSize: '0.72rem', color: '#3b82f6', fontWeight: 600, marginBottom: '0.25rem' }}>{lang === 'zh' ? '市场趋势' : 'TRENDS'}</div>
                        {r.market_trends.map((tr, i) => <div key={i} style={{ fontSize: '0.82rem', color: '#d1d5db' }}>• {tr}</div>)}
                      </div>
                    )}
                    {r.recommendation && <div style={{ fontSize: '0.82rem', color: '#fbbf24', padding: '0.5rem 0.75rem', background: 'rgba(251,191,36,0.08)', borderRadius: '0.4rem', border: '1px solid rgba(251,191,36,0.2)' }}>{r.recommendation}</div>}
                  </div>
                );
              }

              // s3: Subject Lines
              if (skillId === 's3' && r.subjects) {
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    {r.subjects.map((s, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 0.75rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <span style={{ fontSize: '0.78rem', color: '#8b5cf6', fontWeight: 700, flexShrink: 0, minWidth: '1.5rem', textAlign: 'center' }}>{i + 1}</span>
                        <span style={{ fontSize: '0.85rem', color: '#d1d5db', flex: 1 }}>{s.text || s.subject || s.line || JSON.stringify(s)}</span>
                        {s.predicted_open_rate && <span style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 600, flexShrink: 0 }}>{s.predicted_open_rate}</span>}
                      </div>
                    ))}
                  </div>
                );
              }

              // s4: LinkedIn Scripts
              if (skillId === 's4' && r.scripts) {
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {r.scripts.map((s, i) => (
                      <div key={i} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                          <span style={{ fontSize: '0.78rem', color: '#8b5cf6', fontWeight: 600 }}>{s.variant || s.type || `Script ${i+1}`}</span>
                          {s.tone && <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', padding: '0.1rem 0.4rem', borderRadius: '0.3rem', background: 'rgba(255,255,255,0.05)' }}>{s.tone}</span>}
                        </div>
                        {s.opener && <div style={{ fontSize: '0.82rem', color: '#fbbf24', marginBottom: '0.2rem', fontStyle: 'italic' }}>&quot;{s.opener}&quot;</div>}
                        <div className="ai-output-markdown" style={{ fontSize: '0.82rem', color: '#d1d5db', lineHeight: 1.5 }}><ReactMarkdown>{s.body || s.message || s.text || ''}</ReactMarkdown></div>
                        {s.cta && <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginTop: '0.25rem' }}>CTA: {s.cta}</div>}
                      </div>
                    ))}
                  </div>
                );
              }

              // s5: A/B Variants
              if (skillId === 's5' && r.variants) {
                const variantColors = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'];
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {r.variants.map((v, i) => (
                      <div key={i} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                          <span style={{ fontSize: '0.78rem', color: variantColors[i % variantColors.length], fontWeight: 600 }}>Variant {v.variant_id || v.id || String.fromCharCode(65 + i)}</span>
                        </div>
                        <div className="ai-output-markdown" style={{ fontSize: '0.85rem', color: '#d1d5db', lineHeight: 1.5, marginBottom: '0.3rem' }}><ReactMarkdown>{v.text || v.content || v.copy || ''}</ReactMarkdown></div>
                        {v.change_description && <div style={{ fontSize: '0.75rem', color: '#60a5fa' }}>{lang === 'zh' ? '变更: ' : 'Change: '}{v.change_description}</div>}
                        {v.hypothesis && <div style={{ fontSize: '0.75rem', color: '#fbbf24' }}>{lang === 'zh' ? '假设: ' : 'Hypothesis: '}{v.hypothesis}</div>}
                      </div>
                    ))}
                  </div>
                );
              }

              // s6: Lead Scrubber
              if (skillId === 's6' && (r.cleaned_leads || r.issues || r.total !== undefined)) {
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {r.total !== undefined && <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderRadius: '1rem', background: 'rgba(255,255,255,0.06)', color: '#d1d5db', border: '1px solid rgba(255,255,255,0.1)', fontWeight: 600 }}>{lang === 'zh' ? '总计' : 'Total'}: {r.total}</span>}
                      {r.valid !== undefined && <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderRadius: '1rem', background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.25)', fontWeight: 600 }}>{lang === 'zh' ? '有效' : 'Valid'}: {r.valid}</span>}
                      {r.issues_found !== undefined && <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderRadius: '1rem', background: 'rgba(239,68,68,0.1)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)', fontWeight: 600 }}>{lang === 'zh' ? '问题' : 'Issues'}: {r.issues_found}</span>}
                      {r.removed !== undefined && <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderRadius: '1rem', background: 'rgba(239,68,68,0.1)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)', fontWeight: 600 }}>{lang === 'zh' ? '已移除' : 'Removed'}: {Array.isArray(r.removed) ? r.removed.length : r.removed}</span>}
                    </div>
                    {r.issues && r.issues.length > 0 && (
                      <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.4rem', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div style={{ fontSize: '0.72rem', color: '#fca5a5', fontWeight: 600, marginBottom: '0.3rem' }}>{lang === 'zh' ? '发现的问题' : 'ISSUES FOUND'}</div>
                        {r.issues.map((iss, i) => (
                          <div key={i} style={{ fontSize: '0.82rem', color: '#d1d5db', marginBottom: '0.2rem' }}>• <span style={{ color: '#fff' }}>{iss.lead || iss.entry || iss.item || `Item ${i+1}`}</span>: {iss.reason || iss.issue || iss.problem || ''}</div>
                        ))}
                      </div>
                    )}
                    {r.summary && <div style={{ fontSize: '0.82rem', color: '#fbbf24', padding: '0.5rem 0.75rem', background: 'rgba(251,191,36,0.08)', borderRadius: '0.4rem', border: '1px solid rgba(251,191,36,0.2)' }}>{r.summary}</div>}
                  </div>
                );
              }

              // Generic JSON fallback
              return <pre style={{ fontSize: '0.78rem', color: '#d1d5db', whiteSpace: 'pre-wrap', lineHeight: 1.5, margin: 0, fontFamily: 'monospace' }}>{JSON.stringify(r, null, 2)}</pre>;
            };

            return (
              <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                {/* Header row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                  <h2 className="panel-title" style={{ marginBottom: 0 }}>
                    <Sparkles size={22} className="brand-icon" />
                    {lang === 'zh' ? '技能模块 (Skill Modules)' : 'Skill Modules'}
                  </h2>
                  {/* Search box */}
                  <div className="input-group" style={{ width: '320px', margin: 0, position: 'relative' }}>
                    <input
                      type="text"
                      className="input-field"
                      placeholder={lang === 'zh' ? '搜索技能 (名称 / 标签)...' : 'Search skills (name / tag)...'}
                      value={skillSearchQuery}
                      onChange={e => setSkillSearchQuery(e.target.value)}
                      style={{ flex: 1, paddingRight: '2.5rem' }}
                    />
                    <Search size={16} style={{ position: 'absolute', right: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
                  </div>
                </div>
                {/* Sub-description */}
                <div style={{ marginTop: '0.75rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                  {lang === 'zh' ? `共 ${filtered.length} / ${skillsAllSkills.length} 个技能可用` : `${filtered.length} / ${skillsAllSkills.length} skills available`}
                </div>
                {/* Skill cards */}
                <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.6rem', overflowY: 'auto', flex: 1 }}>
                  {filtered.length > 0 ? filtered.map(skill => {
                    const isExpanded = selectedSkill === skill.id;
                    const isRunning = skillRunning === skill.id;
                    const hasResult = skillResult && skillResult.skill_id === skill.id;

                    return (
                      <div key={skill.id} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '0.6rem', border: `1px solid ${isExpanded ? skill.color + '44' : 'rgba(255,255,255,0.06)'}`, transition: 'border-color 0.2s' }}>
                        {/* Card header — clickable */}
                        <button onClick={() => {
                          setSelectedSkill(isExpanded ? null : skill.id);
                          if (!isExpanded) { setSkillResult(null); setSkillInput(''); }
                        }} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 1.1rem', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left' }}>
                          <div style={{ width: 40, height: 40, borderRadius: '0.5rem', background: `${skill.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: skill.color, flexShrink: 0 }}>
                            {skillsIconMap[skill.icon] || <Blocks size={20} />}
                          </div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ color: '#fff', fontWeight: 600, fontSize: '0.9rem' }}>{lang === 'zh' ? skill.nameZh : skill.nameEn}</div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.77rem', marginTop: '0.15rem' }}>{lang === 'zh' ? skill.descZh : skill.descEn}</div>
                          </div>
                          <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '1rem', background: `${skill.color}18`, color: skill.color, fontWeight: 600, flexShrink: 0 }}>{skill.tag}</span>
                          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', transition: 'transform 0.2s', transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', flexShrink: 0 }}>&#9654;</span>
                        </button>

                        {/* Expanded section */}
                        {isExpanded && (
                          <div style={{ padding: '0 1.1rem 1.1rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {/* Input area */}
                            <div style={{ marginTop: '0.75rem' }}>
                              <textarea
                                value={skillInput}
                                onChange={e => setSkillInput(e.target.value)}
                                placeholder={t.skillInputPlaceholder}
                                rows={4}
                                style={{ width: '100%', background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '0.4rem', padding: '0.65rem 0.75rem', color: '#d1d5db', fontSize: '0.85rem', fontFamily: 'inherit', resize: 'vertical', lineHeight: 1.5, boxSizing: 'border-box' }}
                              />
                            </div>

                            {/* Run button */}
                            <button
                              onClick={() => handleRunSkill(skill.id)}
                              disabled={isRunning}
                              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.6rem 1.2rem', background: isRunning ? 'rgba(255,255,255,0.04)' : `${skill.color}20`, color: isRunning ? 'var(--text-muted)' : skill.color, border: `1px solid ${isRunning ? 'rgba(255,255,255,0.08)' : skill.color + '40'}`, borderRadius: '0.4rem', cursor: isRunning ? 'not-allowed' : 'pointer', fontFamily: 'inherit', fontSize: '0.88rem', fontWeight: 600, transition: 'all 0.2s', opacity: isRunning ? 0.7 : 1 }}
                            >
                              {isRunning ? (
                                <>
                                  <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.1)', borderTopColor: skill.color, animation: 'spin 1s linear infinite' }} />
                                  {t.skillRunning}
                                </>
                              ) : (
                                <>
                                  <Activity size={15} />
                                  {t.skillRun}
                                </>
                              )}
                            </button>

                            {/* Result display */}
                            {hasResult && (
                              <div style={{ background: 'rgba(0,0,0,0.15)', borderRadius: '0.5rem', padding: '0.75rem', border: '1px solid rgba(255,255,255,0.04)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                                  <span style={{ fontSize: '0.78rem', color: skill.color, fontWeight: 600 }}>{t.skillResult}</span>
                                  {!skillResult.error && (
                                    <button onClick={() => { navigator.clipboard?.writeText(JSON.stringify(skillResult.result, null, 2)); }} style={{ fontSize: '0.72rem', padding: '0.1rem 0.5rem', borderRadius: '0.3rem', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>
                                      {t.skillCopy}
                                    </button>
                                  )}
                                </div>
                                {renderSkillResult(skillResult, skill.id)}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  }) : (
                    <div style={{ textAlign: 'center', padding: '4rem 2rem', color: 'var(--text-muted)' }}>
                      <Search size={48} style={{ margin: '0 auto 1rem', opacity: 0.15 }} />
                      <p style={{ fontSize: '1rem' }}>{lang === 'zh' ? '没有匹配的技能，请换个关键词试试。' : 'No skills match your search. Try a different keyword.'}</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {activeTab === 'settings' && (() => {
            const sysHealth = [
              { labelZh: 'PostgreSQL 数据库', labelEn: 'PostgreSQL Database', ready: componentReady.database, detailZh: componentReady.database ? '已连接' : '未就绪', detailEn: componentReady.database ? 'Connected' : 'Not ready' },
              { labelZh: 'Playwright 浏览器池', labelEn: 'Playwright Browser Pool', ready: componentReady.browser_pool, detailZh: `${systemStatus?.browser_pool?.total_browsers ?? '-'} / ${systemStatus?.browser_pool?.max_browsers ?? '-'} 实例`, detailEn: `${systemStatus?.browser_pool?.total_browsers ?? '-'} / ${systemStatus?.browser_pool?.max_browsers ?? '-'} instances` },
              { labelZh: '任务执行队列', labelEn: 'Task Execution Queue', ready: componentReady.task_queue, detailZh: `等待 ${systemStatus?.task_queue?.queue_size ?? '-'} · 执行中 ${systemStatus?.task_queue?.active_tasks ?? '-'}`, detailEn: `Pending ${systemStatus?.task_queue?.queue_size ?? '-'} · Active ${systemStatus?.task_queue?.active_tasks ?? '-'}` },
              { labelZh: 'OpenRouter 生成层', labelEn: 'OpenRouter Generation', ready: systemStatus?.ai?.configured, detailZh: systemStatus?.ai?.configured ? '在线生成' : '本地回退', detailEn: systemStatus?.ai?.configured ? 'Online generation' : 'Local fallback' },
            ];
            const envChecks = [
              { key: 'DATABASE_URL', ready: systemStatus?.configuration?.database_url, required: true },
              { key: 'JWT_SECRET_KEY', ready: systemStatus?.configuration?.jwt_secret, required: true },
              { key: 'OPENROUTER_API_KEY', ready: systemStatus?.configuration?.openrouter_api_key, required: false },
              { key: 'CHROME_USER_DATA_DIR', ready: systemStatus?.configuration?.chrome_user_data_dir, required: false },
              { key: 'SCRAPER_PROXY', ready: systemStatus?.configuration?.scraper_proxy, required: false },
            ];
            const sectionLabel = (icon, text) => (
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', marginBottom: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', letterSpacing: '0.03em' }}>
                {icon}{text}
              </h3>
            );
            return (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div className="glass-panel" style={{ padding: '1.1rem 1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <Activity size={18} color={systemStatus?.status === 'healthy' ? 'var(--success)' : '#f59e0b'} />
                  <div style={{ flex: 1 }}>
                    <div style={{ color: '#fff', fontWeight: 700, fontSize: '0.95rem' }}>
                      {lang === 'zh' ? '单机工作台运行时配置' : 'Single-machine Workbench Runtime'}
                    </div>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '0.25rem' }}>
                      {lang === 'zh' ? '本页只展示安全摘要。修改 .env 后执行 scripts/dev.ps1 -Restart 使配置生效。' : 'This page shows safe summaries only. Edit .env and run scripts/dev.ps1 -Restart to apply changes.'}
                    </div>
                  </div>
                  <button className="btn" onClick={fetchSystemStatus} disabled={systemStatusLoading}
                    style={{ background: 'rgba(99,102,241,0.15)', color: 'var(--primary)', border: '1px solid rgba(99,102,241,0.3)', gap: '0.45rem' }}>
                    <RefreshCw size={14} className={systemStatusLoading ? 'loading-spinner' : ''} />
                    {systemStatusLoading ? (lang === 'zh' ? '刷新中' : 'Refreshing') : (lang === 'zh' ? '刷新状态' : 'Refresh Status')}
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Key size={16} color="var(--primary)" />, lang === 'zh' ? '.env 配置检查' : '.env Configuration Check')}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                        {envChecks.map(item => (
                          <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.65rem 0.8rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.45rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: item.ready ? 'var(--success)' : item.required ? '#ef4444' : '#f59e0b', boxShadow: `0 0 6px ${item.ready ? 'var(--success)' : item.required ? '#ef4444' : '#f59e0b'}` }} />
                            <code style={{ flex: 1, color: '#fff', fontSize: '0.8rem' }}>{item.key}</code>
                            <span style={{ fontSize: '0.72rem', color: item.ready ? 'var(--success)' : item.required ? '#f87171' : '#f59e0b' }}>
                              {item.ready ? (lang === 'zh' ? '已配置' : 'Configured') : item.required ? (lang === 'zh' ? '必填' : 'Required') : (lang === 'zh' ? '可选' : 'Optional')}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Terminal size={16} color="var(--accent)" />, lang === 'zh' ? 'AI 路由配置' : 'AI Routing Configuration')}
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', lineHeight: 1.7 }}>
                        <div><span style={{ color: '#fff' }}>Provider:</span> {systemStatus?.ai?.provider || '-'}</div>
                        <div><span style={{ color: '#fff' }}>{lang === 'zh' ? '生成模式' : 'Generation mode'}:</span> {systemStatus?.ai?.mode || '-'}</div>
                        <div><span style={{ color: '#fff' }}>{lang === 'zh' ? '主模型' : 'Primary model'}:</span> <code>{systemStatus?.ai?.marketing_model || '-'}</code></div>
                        <div><span style={{ color: '#fff' }}>{lang === 'zh' ? '回退链' : 'Fallback chain'}:</span> <code>{systemStatus?.ai?.fallback_models?.join(' → ') || '-'}</code></div>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Activity size={16} color="var(--success)" />, lang === 'zh' ? '系统健康状态' : 'System Health')}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                        {sysHealth.map((s, i) => (
                          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', padding: '0.7rem 0.85rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.ready ? 'var(--success)' : '#f59e0b', boxShadow: `0 0 6px ${s.ready ? 'var(--success)' : '#f59e0b'}`, flexShrink: 0 }} />
                            <span style={{ flex: 1, color: '#fff', fontSize: '0.85rem', fontWeight: 500 }}>{lang === 'zh' ? s.labelZh : s.labelEn}</span>
                            <span style={{ fontSize: '0.78rem', color: s.ready ? 'var(--success)' : '#f59e0b', fontFamily: 'monospace' }}>{lang === 'zh' ? s.detailZh : s.detailEn}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Globe size={16} color="#3b82f6" />, lang === 'zh' ? '运行参数' : 'Runtime Parameters')}
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', lineHeight: 1.8 }}>
                        <div><span style={{ color: '#fff' }}>{lang === 'zh' ? '环境' : 'Environment'}:</span> {systemStatus?.environment || '-'}</div>
                        <div><span style={{ color: '#fff' }}>{lang === 'zh' ? '队列并发上限' : 'Queue concurrency'}:</span> {systemStatus?.task_queue?.max_concurrent ?? '-'}</div>
                        <div><span style={{ color: '#fff' }}>Redis:</span> {systemStatus?.task_queue?.use_redis ? (lang === 'zh' ? '已启用' : 'Enabled') : (lang === 'zh' ? '未启用（单机内存队列）' : 'Disabled (in-memory queue)')}</div>
                        <div><span style={{ color: '#fff' }}>Demo mode:</span> {systemStatus?.configuration?.demo_mode ? 'true' : 'false'}</div>
                      </div>
                    </div>
                  </div>
                </div>

                {systemStatusError && <div style={{ color: '#f87171', fontSize: '0.82rem' }}>{systemStatusError}</div>}
              </div>
            );
          })()}

        </div>
      </main>

      {/* Floating Action Button for AI Assistant */}
      <button 
        className={`fab-assistant ${isAssistantOpen ? 'hidden' : ''}`}
        onClick={() => setIsAssistantOpen(true)}
      >
        <Bot size={24} />
      </button>

      {/* AI Assistant Drawer */}
      <div className={`assistant-drawer ${isAssistantOpen ? 'open' : ''}`}>
        <div className="drawer-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Bot size={20} className="brand-icon" />
            <span style={{ fontWeight: 700, letterSpacing: '1px' }}>{t.drawerTitle}</span>
          </div>
          <button className="drawer-close-btn" onClick={() => setIsAssistantOpen(false)}>
            <X size={20} />
          </button>
        </div>
        
        <div className="chat-messages">
          {chatMessages.map((msg, idx) => (
            <div key={idx} className={`chat-bubble ${msg.role === 'user' ? 'user-bubble' : 'ai-bubble'}`}>
              {msg.role === 'assistant' && <Bot size={14} style={{ marginBottom: '0.25rem', opacity: 0.7 }} />}
              <div className="chat-text"><ReactMarkdown>{msg.content}</ReactMarkdown></div>
            </div>
          ))}
          {isTyping && (
            <div className="chat-bubble ai-bubble">
              <div className="typing-dots">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-input-area">
          <input 
            type="text"
            className="chat-input"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder={t.chatPlaceholder}
            disabled={isTyping}
          />
          <button 
            className="chat-send-btn" 
            onClick={handleSendMessage}
            disabled={!chatInput.trim() || isTyping}
          >
            <SendIcon size={18} />
          </button>
        </div>
      </div>

      {/* Plugin Marketplace Modal */}
      {isMarketplaceOpen && (
        <div className="modal-overlay" onClick={() => setIsMarketplaceOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="panel-title" style={{ marginBottom: 0 }}>
                <Blocks size={22} className="brand-icon" />
                {t.marketTitle}
              </h2>
              <button className="drawer-close-btn" onClick={() => setIsMarketplaceOpen(false)}>
                <X size={20} />
              </button>
            </div>
            <div className="modal-body">
              {marketPlugins.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  <Sparkles size={48} style={{ margin: '0 auto 1rem', opacity: 0.5 }} />
                  <p>{lang === 'zh' ? '干得漂亮！您已安装市场上当前所有可用的插件。' : 'You have installed all available plugins in the marketplace!'}</p>
                </div>
              ) : (
                <div className="stats-grid">
                  {marketPlugins.map(plugin => (
                    <div key={plugin.id} className="stat-card" style={{ padding: '1.5rem', background: 'rgba(255,255,255,0.02)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        {renderPluginIcon(plugin.icon, plugin.color)}
                        <span style={{ color: '#fff', fontWeight: 'bold' }}>{plugin.name}</span>
                      </div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem', height: '40px' }}>
                        {lang === 'zh' ? plugin.descZh : plugin.descEn}
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className="badge" style={{ background: 'rgba(255,255,255,0.1)', color: 'var(--text-muted)' }}>
                          {plugin.version}
                        </span>
                        <button 
                          onClick={() => handleInstallPlugin(plugin)}
                          className="btn"
                          style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}
                        >
                          {t.pluginInstall}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
