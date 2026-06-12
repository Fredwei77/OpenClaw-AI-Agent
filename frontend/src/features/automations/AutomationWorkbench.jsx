import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  Bot,
  ChevronRight,
  CircleUserRound,
  Inbox,
  MessageSquare,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  ToggleLeft,
  ToggleRight,
  Trash2,
  UserRoundCheck,
  Workflow,
} from 'lucide-react';

const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://127.0.0.1:8000';

const panel = {
  background: 'rgba(0,0,0,0.22)',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '0.75rem',
  padding: '1rem',
};

const subtleButton = {
  background: 'rgba(255,255,255,0.05)',
  border: '1px solid rgba(255,255,255,0.08)',
  color: '#fff',
  borderRadius: 8,
  padding: '0.52rem 0.72rem',
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
};

const statusColor = (status) => ({
  completed: '#34d399',
  active: '#34d399',
  failed: '#f87171',
  human: '#f59e0b',
  waiting: '#fbbf24',
  suppressed: '#94a3b8',
  running: '#60a5fa',
  urgent: '#f87171',
  high: '#fbbf24',
}[status] || '#9ca3af');

// App owns language selection; this workbench accepts one scalar prop.
// eslint-disable-next-line react/prop-types
function AutomationWorkbench({ lang = 'en' }) {
  const zh = lang === 'zh';
  const [activeView, setActiveView] = useState('overview');
  const [flows, setFlows] = useState([]);
  const [runs, setRuns] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [automationSettings, setAutomationSettings] = useState(null);
  const [aiCalls, setAiCalls] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [webhookSecret, setWebhookSecret] = useState('');
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [message, setMessage] = useState('I need pricing and a demo for our enterprise team today.');
  const [contactName, setContactName] = useState('Demo Buyer');
  const [externalId, setExternalId] = useState('demo-buyer-001');
  const [manualReply, setManualReply] = useState('');
  const [inboxMode, setInboxMode] = useState('all');

  const copy = zh ? {
    title: 'AI 获客自动化',
    subtitle: 'Webhook 模拟、AI 意图评分、人机协同、运行审计与转化分析。',
    overview: '总览',
    flows: '流程',
    inbox: '收件箱',
    runs: '运行审计',
    output: 'AI 与输出',
    refresh: '刷新',
    createAi: '创建 AI 资格审查流程',
    createWelcome: '创建基础欢迎流程',
    simulator: '智能 Webhook 模拟器',
    contact: '联系人名称',
    external: '外部联系人 ID',
    content: '入站消息',
    send: '发送模拟事件',
    metrics: '最近 30 天',
    totalRuns: '自动化运行',
    successRate: '成功率',
    aiMessages: '自动回复',
    handoffs: '人工接管',
    averageScore: '平均线索分',
    noData: '暂无数据',
    automation: '自动化',
    human: '人工',
    all: '全部',
    takeOver: '人工接管',
    release: '恢复自动化',
    reply: '发送人工回复',
    replyPlaceholder: '输入人工回复，此处仍为 Webhook 模拟发送...',
    score: '评分',
    intent: '意图',
    unread: '未读',
    details: '运行详情',
    retry: '重试失败运行',
    eventProcessed: '事件已处理',
    duplicate: '重复事件已忽略',
    save: '保存配置',
    approve: '批准并发送',
    provider: 'AI 提供方',
    replyMode: '回复模式',
    callbackUrl: '出站 Webhook URL',
    callbackSecret: '签名密钥',
    aiCalls: 'AI 调用记录',
    deliveries: '投递记录',
  } : {
    title: 'AI Lead Automation',
    subtitle: 'Webhook simulation, AI intent scoring, human handoff, run auditing, and conversion analytics.',
    overview: 'Overview',
    flows: 'Flows',
    inbox: 'Inbox',
    runs: 'Run audit',
    output: 'AI & Output',
    refresh: 'Refresh',
    createAi: 'Create AI qualification flow',
    createWelcome: 'Create basic welcome flow',
    simulator: 'Intelligent webhook simulator',
    contact: 'Contact name',
    external: 'External contact ID',
    content: 'Inbound message',
    send: 'Send simulated event',
    metrics: 'Last 30 days',
    totalRuns: 'Automation runs',
    successRate: 'Success rate',
    aiMessages: 'Automated replies',
    handoffs: 'Human handoffs',
    averageScore: 'Average lead score',
    noData: 'No data yet',
    automation: 'Automation',
    human: 'Human',
    all: 'All',
    takeOver: 'Take over',
    release: 'Resume automation',
    reply: 'Send human reply',
    replyPlaceholder: 'Type a human reply. Delivery remains simulated through the webhook channel...',
    score: 'Score',
    intent: 'Intent',
    unread: 'Unread',
    details: 'Run details',
    retry: 'Retry failed run',
    eventProcessed: 'Event processed',
    duplicate: 'Duplicate event ignored',
    save: 'Save settings',
    approve: 'Approve and send',
    provider: 'AI provider',
    replyMode: 'Reply mode',
    callbackUrl: 'Outbound webhook URL',
    callbackSecret: 'Signing secret',
    aiCalls: 'AI call history',
    deliveries: 'Delivery history',
  };

  const request = useCallback(async (path, options = {}) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });
    if (response.status === 204) return null;
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || data.detail || 'Request failed');
    return data;
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [flowData, runData, conversationData, analyticsData, settingsData, callData, deliveryData] = await Promise.all([
        request('/api/automations/'),
        request('/api/automations/runs/recent?limit=50'),
        request('/api/conversations/?limit=100'),
        request('/api/automations/analytics?days=30'),
        request('/api/automations/settings'),
        request('/api/automations/ai-calls/recent?limit=20'),
        request('/api/automations/deliveries/recent?limit=20'),
      ]);
      setFlows(flowData.flows || []);
      setRuns(runData || []);
      setConversations(conversationData || []);
      setAnalytics(analyticsData);
      setAutomationSettings(settingsData);
      setAiCalls(callData || []);
      setDeliveries(deliveryData || []);
      setNotice('');
    } catch (error) {
      setNotice(error.message);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const createTemplate = async (type) => {
    setLoading(true);
    try {
      const path = type === 'ai'
        ? '/api/automations/templates/ai-qualification'
        : '/api/automations/templates/welcome';
      await request(path, { method: 'POST' });
      setNotice(zh ? '流程已创建并启用。' : 'Flow created and activated.');
      await loadData();
    } catch (error) {
      setNotice(error.message);
      setLoading(false);
    }
  };

  const toggleFlow = async (flow) => {
    try {
      await request(`/api/automations/${flow.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: flow.status === 'active' ? 'paused' : 'active' }),
      });
      await loadData();
    } catch (error) {
      setNotice(error.message);
    }
  };

  const deleteFlow = async (flowId) => {
    try {
      await request(`/api/automations/${flowId}`, { method: 'DELETE' });
      await loadData();
    } catch (error) {
      setNotice(error.message);
    }
  };

  const simulate = async () => {
    setLoading(true);
    try {
      const result = await request('/api/webhooks/simulate', {
        method: 'POST',
        body: JSON.stringify({
          event_type: 'inbound_message',
          channel: 'webhook',
          contact: {
            external_id: externalId,
            name: contactName,
            tags: ['simulator'],
          },
          message: { content: message },
          metadata: { source: 'automation_workbench' },
        }),
      });
      setNotice(
        result.duplicate
          ? copy.duplicate
          : `${copy.eventProcessed}: ${result.run_ids.length} flow(s), conversation #${result.conversation_id}.`,
      );
      await loadData();
    } catch (error) {
      setNotice(error.message);
      setLoading(false);
    }
  };

  const openConversation = async (conversation) => {
    setSelectedConversation(conversation);
    setActiveView('inbox');
    try {
      const data = await request(`/api/conversations/${conversation.id}/messages`);
      setMessages(data || []);
      if (conversation.unread_count > 0) {
        await request(`/api/conversations/${conversation.id}/read`, { method: 'POST' });
        setConversations((items) => items.map((item) => (
          item.id === conversation.id ? { ...item, unread_count: 0 } : item
        )));
      }
    } catch (error) {
      setNotice(error.message);
    }
  };

  const changeConversationMode = async (mode) => {
    if (!selectedConversation) return;
    try {
      const path = mode === 'human'
        ? `/api/conversations/${selectedConversation.id}/takeover`
        : `/api/conversations/${selectedConversation.id}/release`;
      const updated = await request(path, {
        method: 'POST',
        body: mode === 'human'
          ? JSON.stringify({ reason: 'Taken over from the automation workbench.' })
          : undefined,
      });
      setSelectedConversation(updated);
      await loadData();
    } catch (error) {
      setNotice(error.message);
    }
  };

  const sendManualReply = async () => {
    if (!selectedConversation || !manualReply.trim()) return;
    try {
      const sent = await request(`/api/conversations/${selectedConversation.id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content: manualReply.trim() }),
      });
      setMessages((items) => [...items, sent]);
      setManualReply('');
      setSelectedConversation((item) => ({ ...item, mode: 'human', unread_count: 0 }));
      await loadData();
    } catch (error) {
      setNotice(error.message);
    }
  };

  const openRun = async (run) => {
    try {
      const detail = await request(`/api/automations/runs/${run.id}`);
      setSelectedRun(detail);
      setActiveView('runs');
    } catch (error) {
      setNotice(error.message);
    }
  };

  const retryRun = async () => {
    if (!selectedRun) return;
    try {
      const retried = await request(`/api/automations/runs/${selectedRun.id}/retry`, { method: 'POST' });
      setNotice(zh ? `已创建重试运行 #${retried.id}` : `Created retry run #${retried.id}.`);
      setSelectedRun(null);
      await loadData();
    } catch (error) {
      setNotice(error.message);
    }
  };

  const saveAutomationSettings = async () => {
    if (!automationSettings) return;
    setLoading(true);
    try {
      const payload = {
        ai_provider: automationSettings.ai_provider,
        ai_model: automationSettings.ai_model,
        reply_mode: automationSettings.reply_mode,
        min_confidence: Number(automationSettings.min_confidence),
        handoff_score: Number(automationSettings.handoff_score),
        max_auto_replies_per_hour: Number(automationSettings.max_auto_replies_per_hour),
        blocked_terms: automationSettings.blocked_terms || [],
        outbound_webhook_enabled: automationSettings.outbound_webhook_enabled,
        outbound_webhook_url: automationSettings.outbound_webhook_url,
      };
      if (webhookSecret.trim()) payload.outbound_webhook_secret = webhookSecret.trim();
      const saved = await request('/api/automations/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      setAutomationSettings(saved);
      setWebhookSecret('');
      setNotice(zh ? 'AI 与输出配置已保存。' : 'AI and output settings saved.');
    } catch (error) {
      setNotice(error.message);
    } finally {
      setLoading(false);
    }
  };

  const approveMessage = async (messageId) => {
    try {
      await request(`/api/automations/messages/${messageId}/approve`, { method: 'POST' });
      setNotice(zh ? '消息已进入出站投递队列。' : 'Message queued for outbound delivery.');
      if (selectedConversation) await openConversation(selectedConversation);
      await loadData();
    } catch (error) {
      setNotice(error.message);
    }
  };

  const retryDelivery = async (deliveryId) => {
    try {
      await request(`/api/automations/deliveries/${deliveryId}/retry`, { method: 'POST' });
      await loadData();
    } catch (error) {
      setNotice(error.message);
    }
  };

  const filteredConversations = useMemo(
    () => conversations.filter((item) => inboxMode === 'all' || item.mode === inboxMode),
    [conversations, inboxMode],
  );

  const metricCards = [
    [copy.totalRuns, analytics?.summary?.total_runs ?? 0, Activity, '#60a5fa'],
    [copy.successRate, `${analytics?.summary?.success_rate ?? 0}%`, BarChart3, '#34d399'],
    [copy.aiMessages, analytics?.summary?.automated_messages ?? 0, Bot, '#a78bfa'],
    [copy.handoffs, analytics?.summary?.human_handoffs ?? 0, UserRoundCheck, '#f59e0b'],
    [copy.averageScore, analytics?.summary?.average_lead_score ?? 0, Sparkles, '#f472b6'],
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <header style={{ ...panel, display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ width: 44, height: 44, borderRadius: 12, display: 'grid', placeItems: 'center', background: 'rgba(139,92,246,0.16)', color: '#a78bfa' }}>
          <Workflow size={24} />
        </div>
        <div style={{ minWidth: 260, flex: 1 }}>
          <div style={{ color: '#fff', fontWeight: 700, fontSize: '1.05rem' }}>{copy.title}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginTop: 3 }}>{copy.subtitle}</div>
        </div>
        <button className="btn" onClick={() => createTemplate('ai')} disabled={loading} style={{ display: 'flex', gap: 6 }}>
          <Sparkles size={16} /> {copy.createAi}
        </button>
        <button onClick={loadData} disabled={loading} style={subtleButton}>
          <RefreshCw size={15} className={loading ? 'loading-spinner' : ''} /> {copy.refresh}
        </button>
      </header>

      <nav style={{ display: 'flex', gap: 6, padding: 4, background: 'rgba(255,255,255,0.025)', borderRadius: 10, width: 'fit-content' }}>
        {[
          ['overview', copy.overview, BarChart3],
          ['flows', copy.flows, Workflow],
          ['inbox', copy.inbox, Inbox],
          ['output', copy.output, Settings2],
          ['runs', copy.runs, Activity],
        ].map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setActiveView(id)}
            style={{
              ...subtleButton,
              background: activeView === id ? 'rgba(139,92,246,0.2)' : 'transparent',
              borderColor: activeView === id ? 'rgba(167,139,250,0.35)' : 'transparent',
              color: activeView === id ? '#ddd6fe' : 'var(--text-muted)',
            }}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </nav>

      {notice && (
        <div style={{ padding: '0.7rem 0.9rem', borderRadius: 8, color: '#d8b4fe', background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.25)', fontSize: '0.82rem' }}>
          {notice}
        </div>
      )}

      {activeView === 'overview' && (
        <>
          <section>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{copy.metrics}</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(130px, 1fr))', gap: '0.75rem' }}>
              {metricCards.map(([label, value, Icon, color]) => (
                <div key={label} style={panel}>
                  <Icon size={18} color={color} />
                  <div style={{ color: '#fff', fontSize: '1.35rem', fontWeight: 700, marginTop: 10 }}>{value}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: 2 }}>{label}</div>
                </div>
              ))}
            </div>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 0.9fr) minmax(420px, 1.4fr)', gap: '1rem' }}>
            <section style={panel}>
              <h3 style={{ color: '#fff', margin: '0 0 1rem', display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.95rem' }}>
                <Send size={17} /> {copy.simulator}
              </h3>
              {[
                [copy.contact, contactName, setContactName],
                [copy.external, externalId, setExternalId],
              ].map(([label, value, setter]) => (
                <label key={label} style={{ display: 'block', marginBottom: '0.8rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                  {label}
                  <input className="input-field" value={value} onChange={(event) => setter(event.target.value)} style={{ width: '100%', marginTop: 5, boxSizing: 'border-box' }} />
                </label>
              ))}
              <label style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                {copy.content}
                <textarea className="input-field" value={message} onChange={(event) => setMessage(event.target.value)} rows={5} style={{ width: '100%', marginTop: 5, boxSizing: 'border-box', resize: 'vertical' }} />
              </label>
              <button className="btn" onClick={simulate} disabled={loading || !message.trim() || !externalId.trim()} style={{ width: '100%', marginTop: '0.9rem', justifyContent: 'center', display: 'flex', gap: 7 }}>
                <Play size={16} /> {copy.send}
              </button>
            </section>

            <section style={panel}>
              <h3 style={{ color: '#fff', margin: '0 0 0.9rem', fontSize: '0.95rem' }}>{zh ? '意图分布与流程表现' : 'Intent and flow performance'}</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '0.8fr 1.2fr', gap: '1rem' }}>
                <div>
                  {(analytics?.intent_distribution || []).map((item) => (
                    <div key={item.intent} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.55rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)', color: '#fff', fontSize: '0.8rem' }}>
                      <span>{item.intent}</span><strong>{item.count}</strong>
                    </div>
                  ))}
                  {!analytics?.intent_distribution?.length && <Empty text={copy.noData} />}
                </div>
                <div>
                  {(analytics?.flow_performance || []).slice(0, 6).map((item) => (
                    <div key={item.flow_id} style={{ padding: '0.55rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#fff', fontSize: '0.8rem' }}>
                        <span>{item.flow_name}</span><span>{item.success_rate}%</span>
                      </div>
                      <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 4, marginTop: 7 }}>
                        <div style={{ width: `${item.success_rate}%`, height: '100%', background: '#8b5cf6', borderRadius: 4 }} />
                      </div>
                    </div>
                  ))}
                  {!analytics?.flow_performance?.length && <Empty text={copy.noData} />}
                </div>
              </div>
            </section>
          </div>
        </>
      )}

      {activeView === 'flows' && (
        <section style={panel}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '1rem' }}>
            <h3 style={{ color: '#fff', margin: 0, fontSize: '0.95rem' }}>{copy.flows}</h3>
            <button onClick={() => createTemplate('welcome')} style={{ ...subtleButton, marginLeft: 'auto' }}><Plus size={15} /> {copy.createWelcome}</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
            {flows.map((flow) => (
              <div key={flow.id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.85rem', background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8 }}>
                <button onClick={() => toggleFlow(flow)} title={flow.status} style={{ border: 0, background: 'transparent', color: statusColor(flow.status), cursor: 'pointer', padding: 0 }}>
                  {flow.status === 'active' ? <ToggleRight size={25} /> : <ToggleLeft size={25} />}
                </button>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#fff', fontWeight: 600, fontSize: '0.86rem' }}>{flow.name}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: 3 }}>
                    {flow.trigger_type} · {flow.definition?.steps?.length || 0} steps · v{flow.version}
                  </div>
                </div>
                <span style={{ color: statusColor(flow.status), fontSize: '0.72rem', textTransform: 'uppercase' }}>{flow.status}</span>
                <button onClick={() => deleteFlow(flow.id)} style={{ border: 0, background: 'transparent', color: '#f87171', cursor: 'pointer' }}><Trash2 size={15} /></button>
              </div>
            ))}
            {!flows.length && <Empty text={copy.noData} />}
          </div>
        </section>
      )}

      {activeView === 'inbox' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 0.75fr) minmax(460px, 1.45fr)', gap: '1rem', minHeight: 520 }}>
          <section style={{ ...panel, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '0.8rem', display: 'flex', gap: 6, borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
              {[
                ['all', copy.all],
                ['automation', copy.automation],
                ['human', copy.human],
              ].map(([mode, label]) => (
                <button key={mode} onClick={() => setInboxMode(mode)} style={{ ...subtleButton, padding: '0.35rem 0.55rem', background: inboxMode === mode ? 'rgba(139,92,246,0.18)' : 'transparent' }}>
                  {label}
                </button>
              ))}
            </div>
            <div style={{ maxHeight: 620, overflow: 'auto' }}>
              {filteredConversations.map((conversation) => (
                <button
                  key={conversation.id}
                  onClick={() => openConversation(conversation)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '0.85rem',
                    border: 0,
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                    background: selectedConversation?.id === conversation.id ? 'rgba(139,92,246,0.12)' : 'transparent',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CircleUserRound size={18} color={conversation.mode === 'human' ? '#f59e0b' : '#8b5cf6'} />
                    <strong style={{ color: '#fff', fontSize: '0.82rem', flex: 1 }}>{conversation.contact_name}</strong>
                    {conversation.unread_count > 0 && <span style={{ color: '#fff', background: '#8b5cf6', borderRadius: 10, minWidth: 18, textAlign: 'center', fontSize: '0.65rem', padding: 2 }}>{conversation.unread_count}</span>}
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.71rem', marginTop: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{conversation.last_message}</div>
                  <div style={{ display: 'flex', gap: 7, marginTop: 7, fontSize: '0.65rem' }}>
                    <span style={{ color: statusColor(conversation.mode) }}>{conversation.mode}</span>
                    <span style={{ color: statusColor(conversation.priority) }}>{conversation.priority}</span>
                    <span style={{ color: '#60a5fa' }}>{conversation.intent || 'unknown'}</span>
                    <span style={{ color: '#f472b6', marginLeft: 'auto' }}>{conversation.quality_score}/100</span>
                  </div>
                </button>
              ))}
              {!filteredConversations.length && <div style={{ padding: '1rem' }}><Empty text={copy.noData} /></div>}
            </div>
          </section>

          <section style={{ ...panel, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
            {selectedConversation ? (
              <>
                <div style={{ padding: '0.9rem 1rem', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <MessageSquare size={18} color="#a78bfa" />
                    <strong style={{ color: '#fff' }}>{selectedConversation.contact_name}</strong>
                    <span style={{ color: statusColor(selectedConversation.mode), fontSize: '0.7rem', marginLeft: 4 }}>{selectedConversation.mode}</span>
                    <button
                      onClick={() => changeConversationMode(selectedConversation.mode === 'human' ? 'automation' : 'human')}
                      style={{ ...subtleButton, marginLeft: 'auto' }}
                    >
                      {selectedConversation.mode === 'human' ? <Bot size={15} /> : <UserRoundCheck size={15} />}
                      {selectedConversation.mode === 'human' ? copy.release : copy.takeOver}
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: 12, color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: 8 }}>
                    <span>{copy.intent}: <b style={{ color: '#60a5fa' }}>{selectedConversation.intent || 'unknown'}</b></span>
                    <span>{copy.score}: <b style={{ color: '#f472b6' }}>{selectedConversation.quality_score}/100</b></span>
                    <span>{selectedConversation.channel} · {selectedConversation.external_id}</span>
                  </div>
                  {selectedConversation.ai_summary && <div style={{ color: '#c4b5fd', fontSize: '0.72rem', marginTop: 8 }}>{selectedConversation.ai_summary}</div>}
                  {selectedConversation.handoff_reason && <div style={{ color: '#fbbf24', fontSize: '0.7rem', marginTop: 6 }}>{selectedConversation.handoff_reason}</div>}
                </div>
                <div style={{ flex: 1, minHeight: 300, maxHeight: 430, overflow: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {messages.map((item) => (
                    <div key={item.id} style={{ alignSelf: item.direction === 'outbound' ? 'flex-end' : 'flex-start', maxWidth: '78%' }}>
                      <div style={{ padding: '0.7rem 0.85rem', borderRadius: 12, color: '#fff', fontSize: '0.82rem', lineHeight: 1.45, background: item.direction === 'outbound' ? 'rgba(139,92,246,0.24)' : 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.07)' }}>
                        {item.content}
                      </div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.62rem', marginTop: 4, textAlign: item.direction === 'outbound' ? 'right' : 'left' }}>
                        {item.metadata?.source || item.direction} · {item.status} · {new Date(item.created_at).toLocaleString()}
                      </div>
                      {item.direction === 'outbound' && ['draft', 'pending_review', 'failed'].includes(item.status) && (
                        <button onClick={() => approveMessage(item.id)} style={{ ...subtleButton, marginTop: 5, padding: '0.3rem 0.5rem', fontSize: '0.68rem' }}>
                          <ShieldCheck size={13} /> {copy.approve}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <div style={{ padding: '0.85rem', borderTop: '1px solid rgba(255,255,255,0.07)', display: 'flex', gap: 8 }}>
                  <textarea className="input-field" value={manualReply} onChange={(event) => setManualReply(event.target.value)} placeholder={copy.replyPlaceholder} rows={2} style={{ flex: 1, resize: 'none' }} />
                  <button className="btn" onClick={sendManualReply} disabled={!manualReply.trim()} style={{ alignSelf: 'stretch', display: 'grid', placeItems: 'center' }} title={copy.reply}><Send size={17} /></button>
                </div>
              </>
            ) : (
              <div style={{ margin: 'auto', color: 'var(--text-muted)', textAlign: 'center' }}>
                <Inbox size={34} style={{ marginBottom: 10 }} />
                <div>{zh ? '选择一个会话查看详情' : 'Select a conversation to inspect it'}</div>
              </div>
            )}
          </section>
        </div>
      )}

      {activeView === 'output' && automationSettings && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 0.9fr) minmax(460px, 1.2fr)', gap: '1rem' }}>
          <section style={panel}>
            <h3 style={{ color: '#fff', margin: '0 0 1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Settings2 size={18} /> {copy.output}
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem' }}>
              <Field label={copy.provider}>
                <select className="input-field" value={automationSettings.ai_provider} onChange={(event) => setAutomationSettings({ ...automationSettings, ai_provider: event.target.value })} style={{ width: '100%' }}>
                  <option value="local">Local</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="openrouter" disabled={!automationSettings.openrouter_configured}>OpenRouter</option>
                </select>
              </Field>
              <Field label={copy.replyMode}>
                <select className="input-field" value={automationSettings.reply_mode} onChange={(event) => setAutomationSettings({ ...automationSettings, reply_mode: event.target.value })} style={{ width: '100%' }}>
                  <option value="draft">Draft</option>
                  <option value="review">Review</option>
                  <option value="automatic">Automatic</option>
                </select>
              </Field>
              <Field label={zh ? '模型' : 'Model'}>
                <input className="input-field" value={automationSettings.ai_model} placeholder={automationSettings.default_model} onChange={(event) => setAutomationSettings({ ...automationSettings, ai_model: event.target.value })} style={{ width: '100%', boxSizing: 'border-box' }} />
              </Field>
              <Field label={zh ? '最低置信度' : 'Minimum confidence'}>
                <input className="input-field" type="number" min="0" max="1" step="0.05" value={automationSettings.min_confidence} onChange={(event) => setAutomationSettings({ ...automationSettings, min_confidence: event.target.value })} style={{ width: '100%', boxSizing: 'border-box' }} />
              </Field>
              <Field label={zh ? '转人工评分' : 'Handoff score'}>
                <input className="input-field" type="number" min="0" max="100" value={automationSettings.handoff_score} onChange={(event) => setAutomationSettings({ ...automationSettings, handoff_score: event.target.value })} style={{ width: '100%', boxSizing: 'border-box' }} />
              </Field>
              <Field label={zh ? '每小时自动回复上限' : 'Auto replies per hour'}>
                <input className="input-field" type="number" min="1" max="100" value={automationSettings.max_auto_replies_per_hour} onChange={(event) => setAutomationSettings({ ...automationSettings, max_auto_replies_per_hour: event.target.value })} style={{ width: '100%', boxSizing: 'border-box' }} />
              </Field>
            </div>
            <Field label={zh ? '敏感词（逗号分隔）' : 'Blocked terms (comma separated)'}>
              <input className="input-field" value={(automationSettings.blocked_terms || []).join(', ')} onChange={(event) => setAutomationSettings({ ...automationSettings, blocked_terms: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) })} style={{ width: '100%', boxSizing: 'border-box' }} />
            </Field>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#fff', fontSize: '0.78rem', margin: '0.9rem 0' }}>
              <input type="checkbox" checked={automationSettings.outbound_webhook_enabled} onChange={(event) => setAutomationSettings({ ...automationSettings, outbound_webhook_enabled: event.target.checked })} />
              {zh ? '启用真实出站 Webhook' : 'Enable real outbound webhook'}
            </label>
            <Field label={copy.callbackUrl}>
              <input className="input-field" value={automationSettings.outbound_webhook_url} onChange={(event) => setAutomationSettings({ ...automationSettings, outbound_webhook_url: event.target.value })} placeholder="https://example.com/openclaw/callback" style={{ width: '100%', boxSizing: 'border-box' }} />
            </Field>
            <Field label={`${copy.callbackSecret}${automationSettings.webhook_secret_configured ? (zh ? '（已配置）' : ' (configured)') : ''}`}>
              <input className="input-field" type="password" value={webhookSecret} onChange={(event) => setWebhookSecret(event.target.value)} placeholder={zh ? '留空表示保持现有密钥' : 'Leave blank to keep the existing secret'} style={{ width: '100%', boxSizing: 'border-box' }} />
            </Field>
            <button className="btn" onClick={saveAutomationSettings} disabled={loading} style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}>{copy.save}</button>
          </section>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <section style={panel}>
              <h3 style={{ color: '#fff', margin: '0 0 0.8rem', fontSize: '0.9rem' }}>{copy.aiCalls}</h3>
              {aiCalls.slice(0, 10).map((call) => (
                <div key={call.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, padding: '0.55rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <div><div style={{ color: '#fff', fontSize: '0.76rem' }}>{call.provider} · {call.model}</div><div style={{ color: 'var(--text-muted)', fontSize: '0.66rem' }}>{call.output?.intent || '-'} · {call.latency_ms}ms · {call.prompt_tokens + call.completion_tokens} tokens</div></div>
                  <span style={{ color: statusColor(call.status), fontSize: '0.68rem' }}>{call.status}</span>
                </div>
              ))}
              {!aiCalls.length && <Empty text={copy.noData} />}
            </section>
            <section style={panel}>
              <h3 style={{ color: '#fff', margin: '0 0 0.8rem', fontSize: '0.9rem' }}>{copy.deliveries}</h3>
              {deliveries.slice(0, 10).map((delivery) => (
                <div key={delivery.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.55rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <div style={{ flex: 1 }}><div style={{ color: '#fff', fontSize: '0.76rem' }}>message #{delivery.message_id}</div><div style={{ color: 'var(--text-muted)', fontSize: '0.66rem' }}>{delivery.attempts} attempt(s) · HTTP {delivery.response_status || '-'}</div></div>
                  <span style={{ color: statusColor(delivery.status), fontSize: '0.68rem' }}>{delivery.status}</span>
                  {delivery.status === 'failed' && <button onClick={() => retryDelivery(delivery.id)} style={{ ...subtleButton, padding: 5 }}><RotateCcw size={13} /></button>}
                </div>
              ))}
              {!deliveries.length && <Empty text={copy.noData} />}
            </section>
          </div>
        </div>
      )}

      {activeView === 'runs' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(330px, 0.85fr) minmax(430px, 1.25fr)', gap: '1rem' }}>
          <section style={panel}>
            <h3 style={{ color: '#fff', margin: '0 0 0.8rem', fontSize: '0.95rem' }}>{copy.runs}</h3>
            {runs.map((run) => (
              <button key={run.id} onClick={() => openRun(run)} style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr auto auto', alignItems: 'center', gap: 10, padding: '0.7rem 0', border: 0, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
                <div>
                  <div style={{ color: '#fff', fontSize: '0.8rem' }}>{run.flow_name}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', marginTop: 3 }}>#{run.id} · step {run.current_step}</div>
                </div>
                <span style={{ color: statusColor(run.status), fontSize: '0.7rem' }}>{run.status}</span>
                <ChevronRight size={15} color="#6b7280" />
              </button>
            ))}
            {!runs.length && <Empty text={copy.noData} />}
          </section>

          <section style={panel}>
            {selectedRun ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '1rem' }}>
                  <Activity size={18} color="#a78bfa" />
                  <strong style={{ color: '#fff' }}>{copy.details} #{selectedRun.id}</strong>
                  <span style={{ color: statusColor(selectedRun.status), fontSize: '0.72rem' }}>{selectedRun.status}</span>
                  {selectedRun.status === 'failed' && (
                    <button onClick={retryRun} style={{ ...subtleButton, marginLeft: 'auto' }}><RotateCcw size={15} /> {copy.retry}</button>
                  )}
                </div>
                {selectedRun.error && <div style={{ color: '#fca5a5', background: 'rgba(239,68,68,0.08)', padding: '0.7rem', borderRadius: 7, fontSize: '0.75rem', marginBottom: 10 }}>{selectedRun.error}</div>}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {selectedRun.steps.map((step) => (
                    <div key={step.id} style={{ padding: '0.75rem', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, background: 'rgba(255,255,255,0.02)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ width: 22, height: 22, display: 'grid', placeItems: 'center', borderRadius: 11, background: 'rgba(139,92,246,0.18)', color: '#c4b5fd', fontSize: '0.68rem' }}>{step.step_index + 1}</span>
                        <strong style={{ color: '#fff', fontSize: '0.78rem' }}>{step.step_type}</strong>
                        <span style={{ color: statusColor(step.status), fontSize: '0.68rem', marginLeft: 'auto' }}>{step.status}</span>
                      </div>
                      {step.error && <div style={{ color: '#fca5a5', fontSize: '0.68rem', marginTop: 7 }}>{step.error}</div>}
                      {Object.keys(step.output || {}).length > 0 && (
                        <pre style={{ color: '#94a3b8', fontSize: '0.64rem', margin: '8px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{JSON.stringify(step.output, null, 2)}</pre>
                      )}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '3rem 0' }}>{zh ? '选择一次运行查看逐步审计记录' : 'Select a run to inspect its step audit trail'}</div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

// eslint-disable-next-line react/prop-types
function Empty({ text }) {
  return <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '0.6rem 0' }}>{text}</div>;
}

// eslint-disable-next-line react/prop-types
function Field({ label, children }) {
  return <label style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.72rem', marginBottom: '0.8rem' }}>{label}<div style={{ marginTop: 5 }}>{children}</div></label>;
}

export default AutomationWorkbench;
