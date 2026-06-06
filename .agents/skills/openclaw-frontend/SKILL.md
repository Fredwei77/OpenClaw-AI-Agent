# React 前端开发规范

## 使用场景
当您需要审查、编写或修改 React 前端代码时自动调用此技能。

## 代码规范

### 1. 组件结构
```jsx
// ✅ 正确：分离状态和逻辑
function LeadExtractor() {
  const [leads, setLeads] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchLeads = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/leads/`);
      // ...
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return <div>...</div>;
}

// ❌ 错误：所有逻辑混在一起
function LeadExtractor() {
  const [data, setData] = useState();
  // 大量代码...
  return <div>...</div>;
}
```

### 2. API 调用
```jsx
// ✅ 正确：统一管理 API 调用
const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://127.0.0.1:8000';

async function fetchWithAuth(url, options = {}) {
  const token = localStorage.getItem('token');
  const response = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

// ❌ 错误：重复的 fetch 逻辑
const response = await fetch(url, {
  headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
});
```

### 3. 错误处理
```jsx
// ✅ 正确：使用错误边界和状态
function AnalyticsTab() {
  const [error, setError] = useState('');
  if (error) {
    return <div className="error-state">{error}</div>;
  }
  // ...
}

// ✅ 正确：try/catch/finally
try {
  const data = await fetchData();
  setData(data);
} catch (err) {
  setError(err.message || 'Network error');
} finally {
  setIsLoading(false);
}
```

### 4. 状态管理
```jsx
// ✅ 正确：使用多个 useState 清晰分离
const [activeTab, setActiveTab] = useState('dashboard');
const [keyword, setKeyword] = useState('');
const [isScraping, setIsScraping] = useState(false);
const [leads, setLeads] = useState([]);

// ❌ 错误：使用一个对象管理所有状态
const [state, setState] = useState({
  tab: 'dashboard',
  keyword: '',
  scraping: false,
  leads: []
});
```

### 5. Tailwind CSS 使用
```jsx
// ✅ 正确：使用语义化类名组合
<div className="glass-panel p-6">
  <h2 className="panel-title">
    <Terminal className="brand-icon" />
    {t.panelStream}
  </h2>
</div>

// ❌ 错误：过度嵌套或重复样式
<div className="bg-black bg-opacity-25 rounded-lg border border-white border-opacity-5 p-6">
  <div className="flex items-center justify-between mb-4">
```

### 6. Lucide React 图标
```jsx
// ✅ 正确：按需导入
import { Search, Users, Settings, Bot } from 'lucide-react';

// ❌ 错误：导入整个库
import * as Icons from 'lucide-react';
```

### 7. 国际化 (i18n)
```jsx
// ✅ 正确：使用语言状态切换
const [lang, setLang] = useState('zh');
const t = i18n[lang];

// ❌ 错误：硬编码文本
<span>已完成</span>
```

## 性能优化

1. **useEffect 依赖数组**：确保完整
   ```jsx
   useEffect(() => {
     if (activeTab === 'analytics') fetchAnalytics();
   }, [activeTab, lang]);
   ```

2. **useCallback/useMemo**：用于回调和数据
   ```jsx
   const handleScrape = useCallback(async () => {
     // ...
   }, [keyword, platform]);
   ```

3. **组件懒加载**
   ```jsx
   const AnalyticsTab = lazy(() => import('./AnalyticsTab'));
   ```

## 目录结构
```
frontend/src/
├── App.jsx          # 主应用
├── App.css          # 样式
├── index.css        # 全局样式
└── main.jsx         # 入口
```
