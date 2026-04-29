import { useState, useRef, useEffect } from 'react';
import { LayoutDashboard, Users, Send, Settings, Search, Activity, Box, BarChart3, Loader2, Sparkles, Terminal, Bot, X, Send as SendIcon, Globe, Blocks, Key, TrendingUp, CheckCircle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// Use environment variable for backend URL if available, default to localhost:8000
const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://127.0.0.1:8000';

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
    pluginInstalled: "Installed"
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
    pluginInstalled: "已安装"
  }
};

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [keyword, setKeyword] = useState('fitness equipment');
  const [platform, setPlatform] = useState('x');
  const [isScraping, setIsScraping] = useState(false);
  const [leads, setLeads] = useState([]);
  const [statusMsg, setStatusMsg] = useState('');

  // Auth State
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState(null);
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

  // Settings State
  const [apiKey, setApiKey] = useState('sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx');
  const [isChangingKey, setIsChangingKey] = useState(false);
  const [selectedLlm, setSelectedLlm] = useState('GLM-4-Plus (Zhipu)');
  const [concurrentLimit, setConcurrentLimit] = useState(5);
  const [webhookUrl, setWebhookUrl] = useState('https://your-domain.com/api/webhook');
  const [isTestingWebhook, setIsTestingWebhook] = useState(false);
  const [webhookSuccess, setWebhookSuccess] = useState(false);

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
  const dashboardSystemLogs = [
    { time: '12:07:02', msg: lang === 'zh' ? '[系统] FastAPI 服务已就绪，监听 0.0.0.0:8000' : '[System] FastAPI ready on 0.0.0.0:8000', type: 'success' },
    { time: '12:06:58', msg: lang === 'zh' ? '[代理] Marketing LLM 插件已加载 (v2.0)' : '[Agent] Marketing LLM Plugin loaded (v2.0)', type: 'info' },
    { time: '12:06:55', msg: lang === 'zh' ? '[系统] 数据库连接池初始化，最大并发: 10' : '[System] DB pool init, max_conn: 10', type: 'info' },
    { time: '12:06:50', msg: lang === 'zh' ? '[系统] 加载环境变量完成' : '[System] Env variables loaded', type: 'success' },
    { time: '12:06:48', msg: lang === 'zh' ? '[系统] 启动 Uvicorn 服务器...' : '[System] Starting Uvicorn server...', type: 'info' },
  ];
  const dashboardAgents = [
    { nameZh: '线索提取特工', nameEn: 'Lead Extractor', status: 'idle', descZh: '等待任务部署', descEn: 'Awaiting deployment', color: 'var(--text-muted)' },
    { nameZh: '营销文案智能体', nameEn: 'Marketing Copywriter', status: 'active', descZh: '就绪，等待触发', descEn: 'Ready, awaiting trigger', color: 'var(--success)' },
    { nameZh: 'LLM 路由核心', nameEn: 'LLM Router', status: 'active', descZh: '已连接 OpenRouter', descEn: 'Connected to OpenRouter', color: 'var(--success)' },
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
  ];
  const marketingCampaigns = [
    { nameZh: '健身器材商家拓客行动', nameEn: 'Fitness Equipment Outreach', statsZh: '已发送 142 封 · 打开率 34%', statsEn: 'Sent 142 · Open 34%', status: 'done', pct: 100 },
    { nameZh: 'Shopify 独立站站长邀约', nameEn: 'Shopify Store Owner Invites', statsZh: '已触达 58 人 · 回复 12 人', statsEn: 'Reached 58 · Replies 12', status: 'running', pct: 62 },
    { nameZh: 'SaaS 工具订阅推广', nameEn: 'SaaS Tool Subscription Drive', statsZh: '排队中 · 待发送 230 封', statsEn: 'Queued · 230 emails pending', status: 'queued', pct: 0 },
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
  const fetchAnalytics = async () => {
    setAnalyticsLoading(true);
    setAnalyticsError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE_URL}/api/analytics/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success === false) {
        setAnalyticsError(data.error || 'Failed to load analytics');
      } else {
        setAnalyticsData(data);
      }
    } catch (err) {
      setAnalyticsError(lang === 'zh' ? '网络错误' : 'Network error');
    } finally {
      setAnalyticsLoading(false);
    }
  };

  // Check auth status on mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setIsLoggedIn(true);
      setAuthLoading(false);
    } else {
      setAuthLoading(false);
    }
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
  };

  // Fetch analytics when tab changes to analytics
  useEffect(() => {
    if (activeTab === 'analytics') {
      fetchAnalytics();
    }
  }, [activeTab, lang]);

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
    setLeads([]);

    try {
      const token = localStorage.getItem('token');
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

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      if (result.status === 'success' && result.data && result.data.length > 0) {
        setStatusMsg(`${t.sysSuccess}${result.leads_found}${t.sysSuccessEnd}"${keyword}".`);
        setLeads(result.data);
      } else if (result.status === 'error') {
        setStatusMsg(lang === 'zh' ? `[错误] 爬取失败: ${result.message}` : `[Error] Scraping failed: ${result.message}`);
        // Show demo leads on error for UI demonstration
        setLeads([
          { id: 1, platform: platform || 'x', username: `demo_user_${keyword}`, profile_url: `https://example.com/user/${keyword}`, tags: [keyword, 'demo'], followers: Math.floor(Math.random() * 5000) + 500 },
          { id: 2, platform: platform || 'x', username: `lead_pro_${keyword}`, profile_url: `https://example.com/pro/${keyword}`, tags: [keyword, 'hot'], followers: Math.floor(Math.random() * 10000) + 1000 },
          { id: 3, platform: platform || 'linkedin', username: `${keyword}_expert`, profile_url: `https://linkedin.com/in/${keyword}`, tags: [keyword, 'verified'], followers: Math.floor(Math.random() * 8000) + 2000 },
        ]);
      } else {
        setStatusMsg(lang === 'zh' ? `[提示] 未找到匹配「${keyword}」的线索，已创建模拟数据用于演示` : `[Info] No leads found for "${keyword}", showing demo data.`);
        // Show demo leads for UI demonstration
        setLeads([
          { id: 1, platform: platform || 'x', username: `demo_user_${keyword}`, profile_url: `https://example.com/user/${keyword}`, tags: [keyword, 'demo'], followers: Math.floor(Math.random() * 5000) + 500 },
          { id: 2, platform: platform || 'x', username: `lead_pro_${keyword}`, profile_url: `https://example.com/pro/${keyword}`, tags: [keyword, 'hot'], followers: Math.floor(Math.random() * 10000) + 1000 },
          { id: 3, platform: platform || 'linkedin', username: `${keyword}_expert`, profile_url: `https://linkedin.com/in/${keyword}`, tags: [keyword, 'verified'], followers: Math.floor(Math.random() * 8000) + 2000 },
        ]);
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
    
    let prompt = '';
    const sampleLeads = leads && leads.length > 0 ? JSON.stringify(leads.slice(0, 3)) : '无真实数据（请使用示例假设）';
    
    if (type === 'email') {
      setMarketingActionTitle(lang === 'zh' ? '生成个性化开发信' : 'Generated Cold Email');
      prompt = `基于以下潜在客户数据，生成一封个性化的业务开发信(Cold Email)：\n\n${sampleLeads}\n\n要求：专业、有吸引力，且能体现出你对他们的了解。如果没客户数据，请生成一个吸引目标领域客户的通用高质量开发信。`;
    } else if (type === 'classify') {
      setMarketingActionTitle(lang === 'zh' ? '批量潜在客户分类' : 'Lead Classification Results');
      prompt = `请根据以下潜在客户列表，分析他们的意向度和可能感兴趣的产品方向，将其分为“高意向”、“中意向”、“低意向”三类，并给出简明理由：\n\n${sampleLeads}\n\n如果没有真实客户数据，请输出一个包含三个虚构客户的示例分类结果。`;
    } else if (type === 'social') {
      setMarketingActionTitle(lang === 'zh' ? 'AI 社交媒体跟进' : 'Social Media Follow-up');
      prompt = `基于以下客户信息，起草3条可以在社交媒体（如Twitter/LinkedIn）上用来跟进他们或引起他们注意的高互动评论或私信模板：\n\n${sampleLeads}\n\n如果没有客户数据，请生成给目标领域专业人士或KOL的示例通用跟进私信。`;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/agents/test-llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      const data = await response.json();
      if (data.status === 'success') {
        setMarketingResult(data.reply);
      } else {
        setMarketingResult(`[Error] ${data.message}`);
      }
    } catch (err) {
      setMarketingResult(t.sysErrorNet || 'Network Error, please ensure backend is running.');
    } finally {
      setMarketingLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || isTyping) return;
    
    const userMsg = { role: 'user', content: chatInput.trim() };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/agents/test-llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMsg.content })
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      } else {
        setChatMessages(prev => [...prev, { role: 'assistant', content: `[Error] ${data.message}` }]);
      }
    } catch (err) {
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

  const handleTestWebhook = () => {
    setIsTestingWebhook(true);
    setWebhookSuccess(false);
    // Simulate network delay
    setTimeout(() => {
      setIsTestingWebhook(false);
      setWebhookSuccess(true);
      setTimeout(() => setWebhookSuccess(false), 3000);
    }, 1500);
  };

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
             activeTab === 'analytics' ? t.tabAnalytics : t.tabSettings}
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
            <div className="status-indicator">
              <span className="pulse"></span> {t.serverIntegrity}
            </div>
          </div>
        </header>

        <div className="content-body">
          {activeTab === 'dashboard' && (
              <>
                {/* ── Row 1: Stat Cards ── */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                  {[
                    { labelZh: '已提取线索', labelEn: 'Leads Extracted', value: leads.length, sub: lang === 'zh' ? '本次会话' : 'this session', icon: <Users size={20} />, color: 'var(--primary)', glow: 'rgba(99,102,241,0.3)' },
                    { labelZh: '系统健康度', labelEn: 'System Health', value: lang === 'zh' ? '极佳' : 'Optimal', sub: 'uptime 100%', icon: <Activity size={20} />, color: 'var(--success)', glow: 'rgba(16,185,129,0.3)' },
                    { labelZh: '活跃代理数', labelEn: 'Active Agents', value: '2', sub: '/ 3 total', icon: <Bot size={20} />, color: 'var(--accent)', glow: 'rgba(249,115,22,0.3)' },
                    { labelZh: '可用技能', labelEn: 'Skills Available', value: '6', sub: lang === 'zh' ? '全部就绪' : 'all ready', icon: <Sparkles size={20} />, color: '#8b5cf6', glow: 'rgba(139,92,246,0.3)' },
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
                          "{keyword}"
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

                  {leads.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', overflowY: 'auto' }}>
                      {leads.map((lead, idx) => {
                        const platformColor = lead.platform === 'x' ? '#1d9bf0' : lead.platform === 'linkedin' ? '#0a66c2' : '#96bf48';
                        return (
                          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.9rem 1.1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)', transition: 'border-color 0.2s' }}
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
                    <button key={a.type} onClick={() => handleMarketingAction(a.type)} disabled={marketingLoading}
                        style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.1rem', background: marketingLoading ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.2)', border: `1px solid rgba(255,255,255,0.07)`, borderRadius: '0.6rem', cursor: marketingLoading ? 'not-allowed': 'pointer', fontFamily: 'inherit', transition: 'all 0.2s', textAlign: 'left', opacity: marketingLoading ? 0.6 : 1, position: 'relative', overflow: 'hidden' }}
                        onMouseOver={e => { if (!marketingLoading) { e.currentTarget.style.borderColor = a.color + '55'; e.currentTarget.style.background = `${a.glow.replace('0.3', '0.08')}`; }}}
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
                      {marketingResult && !marketingLoading && (
                        <button onClick={() => { navigator.clipboard?.writeText(marketingResult); }} style={{ marginLeft: 'auto', fontSize: '0.75rem', padding: '0.2rem 0.6rem', borderRadius: '0.3rem', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-muted)', cursor: 'pointer', fontFamily: 'inherit' }}>
                          {lang === 'zh' ? '复制' : 'Copy'}
                        </button>
                      )}
                    </h2>

                    {marketingLoading ? (
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
                        <div style={{ flex: 1, overflowY: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.88rem', color: '#d1d5db', lineHeight: 1.7, padding: '0.25rem 0' }}>
                          {marketingResult}
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
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {marketingCampaigns.map((c, i) => {
                      const s = marketingStatusStyle[c.status];
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.85rem 1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ color: '#fff', fontWeight: 500, fontSize: '0.9rem' }}>{lang === 'zh' ? c.nameZh : c.nameEn}</div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '0.3rem' }}>{lang === 'zh' ? c.statsZh : c.statsEn}</div>
                          </div>
                          {/* Progress bar */}
                          {c.status !== 'queued' && (
                            <div style={{ width: 80, flexShrink: 0 }}>
                              <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 99, overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${c.pct}%`, background: c.status === 'done' ? 'var(--success)' : '#60a5fa', borderRadius: 99, transition: 'width 0.5s' }} />
                              </div>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem', textAlign: 'right' }}>{c.pct}%</div>
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
                {/* Skill cards grid */}
                <div className="stats-grid" style={{ marginTop: '1.5rem' }}>
                  {filtered.length > 0 ? filtered.map(skill => (
                    <div key={skill.id} className="stat-card" style={{ padding: '1.5rem', background: 'rgba(0,0,0,0.2)', transition: 'transform 0.2s, box-shadow 0.2s' }}
                      onMouseOver={e => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = `0 8px 24px rgba(0,0,0,0.4)`; }}
                      onMouseOut={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = ''; }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ color: skill.color }}>{skillsIconMap[skill.icon] || <Blocks size={20} />}</span>
                          <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.95rem' }}>{lang === 'zh' ? skill.nameZh : skill.nameEn}</span>
                        </div>
                        <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '0.15rem 0.55rem', borderRadius: '1rem', background: 'rgba(255,255,255,0.07)', color: 'var(--text-muted)', border: '1px solid rgba(255,255,255,0.1)', letterSpacing: '0.05em' }}>{skill.tag}</span>
                      </div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginBottom: '1.25rem', minHeight: '40px', lineHeight: 1.55 }}>
                        {lang === 'zh' ? skill.descZh : skill.descEn}
                      </div>
                      <button className="btn" style={{ width: '100%', background: `rgba(${skill.color === 'var(--primary)' ? '99,102,241' : skill.color === 'var(--success)' ? '16,185,129' : skill.color === 'var(--accent)' ? '249,115,22' : '99,102,241'},0.12)`, color: skill.color, border: `1px solid ${skill.color}30`, gap: '0.4rem' }}
                        onClick={() => alert(lang === 'zh' ? `正在执行：${skill.nameZh}` : `Running: ${skill.nameEn}`)}
                      >
                        <Activity size={15} />
                        {lang === 'zh' ? '执行技能' : 'Run Skill'}
                      </button>
                    </div>
                  )) : (
                    <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '4rem 2rem', color: 'var(--text-muted)' }}>
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
              { labelZh: 'FastAPI 后端', labelEn: 'FastAPI Backend', status: 'online', uptimeZh: '运行 1h 24m', uptimeEn: 'Up 1h 24m' },
              { labelZh: 'Playwright 引擎', labelEn: 'Playwright Engine', status: 'online', uptimeZh: '待机', uptimeEn: 'Standby' },
              { labelZh: 'LLM 连接层', labelEn: 'LLM Gateway', status: 'online', uptimeZh: '响应 < 1s', uptimeEn: 'Latency < 1s' },
              { labelZh: '代理线程池', labelEn: 'Agent Thread Pool', status: 'idle', uptimeZh: '3/8 线程', uptimeEn: '3/8 Threads' },
            ];
            const llmOptions = ['GPT-4o (OpenAI)', 'Claude 3.5 Sonnet (Anthropic)', 'Gemini 2.5 Flash (Google)', 'GLM-4-Plus (Zhipu)'];
            const sectionLabel = (icon, text) => (
              <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#fff', marginBottom: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', letterSpacing: '0.03em' }}>
                {icon}{text}
              </h3>
            );
            return (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* ── Row 1: Two-column (Config + System Health) ── */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  {/* Left: Config Sections */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {/* API Key Section */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Key size={16} color="var(--primary)" />, t.settingsApiKey)}
                      <div style={{ position: 'relative', marginBottom: '0.75rem' }}>
                        <input type={isChangingKey ? 'text' : 'password'} defaultValue={apiKey} onChange={e => setApiKey(e.target.value)} disabled={!isChangingKey} className="input-field"
                          style={{ width: '100%', boxSizing: 'border-box', paddingRight: isChangingKey ? '1rem' : '6rem', opacity: isChangingKey ? 1 : 0.7 }} />
                        {!isChangingKey && (
                          <span style={{ position: 'absolute', right: '0.9rem', top: '50%', transform: 'translateY(-50%)', fontSize: '0.72rem', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', padding: '0.1rem 0.5rem', borderRadius: '0.3rem', border: '1px solid rgba(255,255,255,0.08)' }}>sk-···</span>
                        )}
                      </div>
                      <button className="btn" onClick={() => setIsChangingKey(!isChangingKey)}
                        style={{ background: isChangingKey ? 'rgba(16,185,129,0.15)' : 'rgba(99,102,241,0.15)', color: isChangingKey ? 'var(--success)' : 'var(--primary)', border: `1px solid ${isChangingKey ? 'rgba(16,185,129,0.3)' : 'rgba(99,102,241,0.3)'}`, gap: '0.5rem' }}>
                        <Key size={14} />
                        {isChangingKey ? (lang === 'zh' ? '保存密钥' : 'Save Key') : t.settingsUpdateKey}
                      </button>
                    </div>

                    {/* Agent Settings */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Terminal size={16} color="var(--accent)" />, t.settingsAgent)}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 500 }}>{t.settingsLlm}</label>
                          <select className="input-field" style={{ width: '100%', boxSizing: 'border-box' }} value={selectedLlm} onChange={e => setSelectedLlm(e.target.value)}>
                            {llmOptions.map(o => <option key={o} value={o}>{o}</option>)}
                          </select>
                        </div>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 500 }}>{t.settingsConcurrent}</label>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <input type="range" min={1} max={16} value={concurrentLimit} onChange={e => setConcurrentLimit(e.target.value)} style={{ flex: 1, accentColor: 'var(--accent)', cursor: 'pointer' }} />
                            <span style={{ color: '#fff', fontWeight: 700, fontSize: '1rem', minWidth: '2rem', textAlign: 'center' }}>{concurrentLimit}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right: System Health + Webhook */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {/* System Health */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Activity size={16} color="var(--success)" />, lang === 'zh' ? '系统健康状态' : 'System Health')}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                        {sysHealth.map((s, i) => (
                          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', padding: '0.7rem 0.85rem', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.status === 'online' ? 'var(--success)' : '#f59e0b', boxShadow: `0 0 6px ${s.status === 'online' ? 'var(--success)' : '#f59e0b'}`, flexShrink: 0, animation: s.status === 'online' ? 'none' : undefined }} />
                            <span style={{ flex: 1, color: '#fff', fontSize: '0.85rem', fontWeight: 500 }}>{lang === 'zh' ? s.labelZh : s.labelEn}</span>
                            <span style={{ fontSize: '0.78rem', color: s.status === 'online' ? 'var(--success)' : '#f59e0b', fontFamily: 'monospace' }}>{lang === 'zh' ? s.uptimeZh : s.uptimeEn}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Webhook / Network */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                      {sectionLabel(<Globe size={16} color="#3b82f6" />, t.settingsNetwork)}
                      <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 500 }}>Webhook URL</label>
                      <div style={{ display: 'flex', gap: '0.6rem' }}>
                        <input type="text" value={webhookUrl} onChange={e => setWebhookUrl(e.target.value)} className="input-field" style={{ flex: 1, fontSize: '0.85rem' }} />
                        <button className="btn" onClick={handleTestWebhook} disabled={isTestingWebhook}
                          style={{ flexShrink: 0, background: webhookSuccess ? 'rgba(16,185,129,0.15)' : 'rgba(255,255,255,0.07)', color: webhookSuccess ? 'var(--success)' : '#fff', border: `1px solid ${webhookSuccess ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.1)'}`, gap: '0.4rem' }}>
                          {isTestingWebhook ? <><Loader2 size={14} className="loading-spinner" /> {t.settingsTesting}</> : webhookSuccess ? <><Activity size={14} /> {t.settingsSuccess}</> : t.settingsTestConn}
                        </button>
                      </div>
                      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.6rem', lineHeight: 1.5 }}>
                        {lang === 'zh' ? '成功抓取后将 Webhook 事件推送至此 URL，可接入 Zapier、n8n 等自动化工具。' : 'Trigger Webhook events after successful scrapes. Integrate with Zapier, n8n, or any HTTP endpoint.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* ── Row 2: Danger Zone ── */}
                <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', border: '1px solid rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.03)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ color: '#f87171', fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.25rem' }}>{lang === 'zh' ? '⚠ 危险区域' : '⚠ Danger Zone'}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{lang === 'zh' ? '以下操作不可撤销，请谨慎操作' : 'The following actions are irreversible. Proceed with caution.'}</div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.6rem' }}>
                      <button style={{ padding: '0.4rem 1rem', fontSize: '0.8rem', fontWeight: 600, borderRadius: '0.4rem', cursor: 'pointer', fontFamily: 'inherit', background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}
                        onClick={() => confirm(lang === 'zh' ? '确认清空所有线索数据？' : 'Clear all lead data?')}>
                        {lang === 'zh' ? '清除线索数据' : 'Clear Lead Data'}
                      </button>
                      <button style={{ padding: '0.4rem 1rem', fontSize: '0.8rem', fontWeight: 600, borderRadius: '0.4rem', cursor: 'pointer', fontFamily: 'inherit', background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}
                        onClick={() => confirm(lang === 'zh' ? '确认重置所有设置？' : 'Reset all settings to defaults?')}>
                        {lang === 'zh' ? '恢复出厂设置' : 'Reset to Defaults'}
                      </button>
                    </div>
                  </div>
                </div>
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
              <div className="chat-text">{msg.content}</div>
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
