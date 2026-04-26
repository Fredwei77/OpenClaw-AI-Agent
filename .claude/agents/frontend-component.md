# Frontend Component Reviewer

## Use Scene
当需要创建或修改 React 组件时使用此子代理。

## 职责

### 1. 状态管理检查
```jsx
// ✅ 正确：清晰的多个 useState
function LeadExtractor() {
  const [leads, setLeads] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [keyword, setKeyword] = useState('');
  // ...
}

// ❌ 错误：单一对象管理所有状态
function LeadExtractor() {
  const [state, setState] = useState({
    leads: [],
    loading: false,
    error: null,
    keyword: ''
  });
}

// ✅ 正确：使用 useCallback 包装事件处理
const handleScrape = useCallback(async () => {
  setIsLoading(true);
  try {
    const response = await fetchLeads(keyword);
    setLeads(response);
  } catch (err) {
    setError(err.message);
  } finally {
    setIsLoading(false);
  }
}, [keyword]);

// ❌ 错误：每次渲染创建新函数
<button onClick={() => handleScrape(keyword)}>
```

### 2. API 调用检查
```jsx
// ✅ 正确：错误处理 + 加载状态 + token
const fetchLeads = async (searchParams) => {
  setIsLoading(true);
  setError(null);

  try {
    const token = localStorage.getItem('token');
    const response = await fetch(
      `${API_BASE_URL}/api/leads/?${searchParams}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.leads || [];
  } catch (err) {
    setError(err.message);
    console.error('Failed to fetch leads:', err);
    return [];
  } finally {
    setIsLoading(false);
  }
};

// ❌ 错误：缺少错误处理
const fetchLeads = async () => {
  const response = await fetch(`${API_BASE_URL}/api/leads/`);
  return response.json();
};
```

### 3. 渲染性能
```jsx
// ✅ 正确：大列表使用虚拟滚动
import { FixedSizeList } from 'react-window';

function LeadsList({ leads }) {
  return (
    <FixedSizeList
      height={400}
      itemCount={leads.length}
      itemSize={80}
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>
          <LeadCard lead={leads[index]} />
        </div>
      )}
    </FixedSizeList>
  );
}

// ❌ 错误：直接渲染大量数据
function LeadsList({ leads }) {
  return (
    <div>
      {leads.map(lead => (
        <LeadCard key={lead.id} lead={lead} />
      ))}
    </div>
  );
}
```

### 4. Tailwind CSS 规范
```jsx
// ✅ 正确：语义化类名组合
<div className="glass-panel p-6">
  <h2 className="panel-title">
    <Terminal className="brand-icon" />
    {t.panelStream}
  </h2>
</div>

// ❌ 错误：过度嵌套或重复样式
<div className="bg-black bg-opacity-25 rounded-lg border border-white border-opacity-5 p-6">
  <div className="flex items-center justify-between mb-4">
    <div className="text-xl font-bold">{title}</div>
  </div>
</div>

// ✅ 正确：使用 CSS 变量保持一致性
<div style={{ background: 'rgba(0,0,0,0.25)' }}>
// 或
<div className="glass-panel">
```

### 5. 可访问性
```jsx
// ✅ 正确：语义化 HTML + ARIA
<button
  onClick={handleSubmit}
  disabled={isLoading}
  aria-label={lang === 'zh' ? '提交表单' : 'Submit form'}
>
  {isLoading ? <Loader /> : <SendIcon />}
</button>

// ❌ 错误：使用 div 代替按钮
<div onClick={handleSubmit}>Submit</div>

// ✅ 正确：表单关联 label
<label htmlFor="keyword" className="input-label">
  {t.keyword}
</label>
<input
  id="keyword"
  type="text"
  className="input-field"
  value={keyword}
  onChange={e => setKeyword(e.target.value)}
/>
```

### 6. 组件结构检查
```jsx
// ✅ 正确：清晰的文件结构
components/
├── LeadExtractor/
│   ├── LeadExtractor.jsx    # 主组件
│   ├── LeadCard.jsx         # 子组件
│   ├── LeadList.jsx         # 列表组件
│   └── index.js             # 导出
├── MarketingPanel/
│   └── ...
└── hooks/
    ├── useLeads.js          # 自定义 hooks
    └── useAuth.js

// ✅ 正确：组件保持简洁（< 200 行）
// 如果组件过大，考虑拆分
```

## 检查清单

### 状态管理
- [ ] 多个 useState vs 单个对象（清晰优先）
- [ ] useCallback 用于事件处理
- [ ] useMemo 用于计算结果

### API 调用
- [ ] try/catch 错误处理
- [ ] 加载状态
- [ ] Token 正确获取

### 渲染性能
- [ ] 大列表虚拟化（> 50 项）
- [ ] React.memo 避免不必要重渲染
- [ ] 懒加载组件

### 可访问性
- [ ] 语义化 HTML
- [ ] ARIA 标签
- [ ] 键盘导航

### Tailwind CSS
- [ ] 语义化类名
- [ ] 一致的间距
- [ ] 暗色模式考虑
