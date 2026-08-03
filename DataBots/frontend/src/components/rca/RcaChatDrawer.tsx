import React, { useState } from 'react';
import { ChatMessage } from '../../types';
import { sendChatMessage } from '../../services/api';
import { Sparkles, Send, Terminal, XCircle, Bot, User, CheckCircle2, Search } from 'lucide-react';

interface RcaChatDrawerProps {
  onClose: () => void;
}

const QUICK_PROMPTS = [
  "Verify Revenue Spike (2026-06-21 to 2026-06-26)",
  "Query Approved RCA Findings in ClickHouse",
  "Break down top revenue contributing segments",
  "Verify if eCPM pricing change was ruled out",
];

export const RcaChatDrawer: React.FC<RcaChatDrawerProps> = ({ onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-1',
      sender: 'assistant',
      text: 'Hello! I am your ClickHouse MCP & DeepSeek ReAct follow-up agent. I can access ClickHouse Cloud tables and approved RCA vectors/findings to answer your questions or verify metric spikes.',
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSendPrompt = async (promptText: string) => {
    if (!promptText.trim() || loading) return;
    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: promptText,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const res = await sendChatMessage(promptText);
    setMessages((prev) => [...prev, res]);
    setLoading(false);
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] bg-white border-l border-slate-200 shadow-2xl z-50 flex flex-col animate-slide-in-r">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-600">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">ClickHouse MCP Chat Agent</h3>
            <span className="text-[11px] text-slate-400">DeepSeek ReAct · Vector &amp; SQL Query Agent</span>
          </div>
        </div>
        <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors">
          <XCircle className="w-5 h-5" />
        </button>
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-4 py-2.5 bg-slate-50/50 border-b border-slate-200 flex items-center gap-1.5 overflow-x-auto">
        <span className="text-[10px] font-semibold uppercase text-slate-400 shrink-0">Quick Verify:</span>
        {QUICK_PROMPTS.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => handleSendPrompt(prompt)}
            disabled={loading}
            className="px-2.5 py-1 rounded-md bg-white border border-slate-200 hover:border-brand-300 text-[11px] font-medium text-slate-700 hover:text-brand-600 shrink-0 shadow-sm transition-all disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Messages Feed */}
      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3 ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                msg.sender === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-brand-600 border border-slate-200'
              }`}
            >
              {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`space-y-1.5 max-w-[84%] ${msg.sender === 'user' ? 'text-right' : ''}`}>
              <div
                className={`p-3 rounded-2xl text-xs leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-brand-600 text-white rounded-tr-none shadow-sm'
                    : 'bg-white text-slate-800 border border-slate-200 rounded-tl-none shadow-sm'
                }`}
              >
                {msg.text}
              </div>

              {/* Render SQL Query if tool was invoked */}
              {msg.sqlQuery && (
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-700 text-[11px] font-mono text-emerald-400 space-y-1 text-left shadow-sm">
                  <div className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Terminal className="w-3 h-3 text-emerald-400" /> ClickHouse SQL Verification Query:
                  </div>
                  <div className="overflow-x-auto whitespace-pre-wrap">{msg.sqlQuery}</div>
                </div>
              )}

              <span className="text-[10px] text-slate-400 block px-1">{msg.timestamp}</span>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-brand-600 animate-pulse p-2">
            <Sparkles className="w-4 h-4 animate-spin text-brand-600" /> Querying ClickHouse MCP & DeepSeek...
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-200 bg-white">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendPrompt(input);
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask follow-up (e.g. Verify revenue spike 2026-06-21)..."
            className="flex-1 bg-white text-xs text-slate-900 border border-slate-300 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-300 placeholder:text-slate-400"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white disabled:opacity-50 transition-colors shadow-sm"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
