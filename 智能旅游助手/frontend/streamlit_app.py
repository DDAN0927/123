"""旅游智能助手 — Streamlit 前端（现代旅行主题 · DeepSeek 深度思考版）
启动: streamlit run frontend/streamlit_app.py
"""
import html as _html
import json
import math
import os
import re
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components

try:  # 城市按拼音首字母分组；未安装时回退为单级下拉
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None

try:  # 读取 .env 配置（BAIDU_MAP_AK 等；已存在的环境变量优先）
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

st.set_page_config(page_title="旅游智能助手", page_icon="✈️", layout="wide",
                   initial_sidebar_state="collapsed")

API = os.environ.get("API_URL", "http://localhost:8000")

# Agent 团队信息（icon, title, color）
TEAM = {
    "supervisor": ("🧭", "调度中心", "#6366f1"),
    "planner": ("🗓️", "行程规划师", "#0ea5e9"),
    "attractions": ("🏛️", "景点顾问", "#8b5cf6"),
    "food": ("🍜", "美食顾问", "#f97316"),
    "analyst": ("📊", "数据分析师", "#10b981"),
    "consultant": ("💬", "旅行咨询师", "#ec4899"),
    "FINISH": ("✅", "汇总完成", "#22c55e"),
}


def esc(s: str) -> str:
    return _html.escape(str(s or ""))


def agent_label(name: str) -> str:
    icon, title, _ = TEAM.get(name, ("🤖", name, "#64748b"))
    return f"{icon} {title}"


# ======================================================================
# 全局主题样式
# ======================================================================
def load_css():
    st.markdown("""
<style>
/* ============ 基础 ============ */
html, body, .stApp, [class*="css"] {
    font-family: "Yuanti SC", "幼圆", "YouYuan", "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
}
.stApp {
    background:
        radial-gradient(circle at 24px 32px, rgba(255,210,30,.18) 5px, transparent 6px),
        radial-gradient(circle at 84px 78px, rgba(255,77,77,.10) 4px, transparent 5px),
        radial-gradient(circle at 48px 96px, rgba(93,184,255,.12) 4px, transparent 5px),
        linear-gradient(165deg, #fffbe9 0%, #fff2d0 100%);
    background-size: 130px 130px, 130px 130px, 130px 130px, auto;
}
.block-container { padding-top: 1.1rem; max-width: 1100px; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #cbd8e6; border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: #a9bed4; }
::-webkit-scrollbar-track { background: transparent; }

/* ============ Markdown 排版 ============ */
.stApp h1 { font-weight: 800; letter-spacing: -.5px; }
.stApp h2, .stApp h3 { font-weight: 700; letter-spacing: -.2px; }

/* ============ 侧边栏（蜡笔小新 · 奶油黄） ============ */
section[data-testid="stSidebar"] {
    background: linear-gradient(185deg, #fff9e0 0%, #ffefc0 70%, #ffe8ad 100%);
    border-right: 3px solid #2b2b2b;
}
section[data-testid="stSidebar"] * { color: #4a3728; }
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #2b1d0e; }

.brand { display:flex; align-items:center; gap:12px; padding: 6px 2px 2px; }
.brand-logo {
    width:46px; height:46px; border-radius:50%; flex-shrink:0;
    background: #ffd21e;
    border: 2.5px solid #2b2b2b;
    display:flex; align-items:center; justify-content:center; font-size:24px;
    box-shadow: 3px 3px 0 #2b2b2b;
}
.brand-name { font-size:1.12rem; font-weight:800; color:#2b1d0e; line-height:1.25; }
.brand-sub { font-size:.7rem; color:#a4752f; letter-spacing:.4px; font-weight:600; }

.side-card {
    background: rgba(255,255,255,.75);
    border: 2px solid #2b2b2b;
    border-radius: 14px; padding: 12px 14px; margin: 8px 0;
    box-shadow: 3px 3px 0 rgba(43,43,43,.85);
}
.sc-title {
    color:#b3541e; font-size:.68rem; font-weight:800;
    letter-spacing:1px; margin-bottom:8px;
}
.side-row { display:flex; justify-content:space-between; align-items:center;
            padding:3px 0; font-size:.82rem; color:#6b4f2a; gap:8px; }
.side-row b { color:#2b1d0e; font-weight:700; }
.online-dot { width:9px; height:9px; border-radius:50%; background:#2ecc40;
              display:inline-block; margin-right:6px; border:1.5px solid #2b2b2b; animation: glow 1.9s infinite; }
.offline-dot { width:9px; height:9px; border-radius:50%; background:#ff4d4d;
               display:inline-block; margin-right:6px; border:1.5px solid #2b2b2b; }
@keyframes glow {
    0%   { box-shadow: 0 0 0 0 rgba(46,204,64,.55); }
    70%  { box-shadow: 0 0 0 9px rgba(46,204,64,0); }
    100% { box-shadow: 0 0 0 0 rgba(46,204,64,0); }
}
.think-badge {
    display:inline-flex; align-items:center; gap:6px; margin-top:8px;
    background: #ffd21e;
    border:2px solid #2b2b2b; color:#2b1d0e;
    padding:4px 12px; border-radius:999px; font-size:.74rem; font-weight:800;
    box-shadow: 2px 2px 0 #2b2b2b;
}

.team-item { display:flex; gap:10px; align-items:flex-start; padding:7px 2px;
             border-bottom:2px dashed rgba(43,43,43,.18); }
.team-item:last-child { border-bottom:none; }
.ti-icon { font-size:1.12rem; margin-top:1px; }
.ti-name { color:#2b1d0e; font-size:.85rem; font-weight:700; }
.ti-desc { color:#8a6a3b; font-size:.72rem; line-height:1.45; }

/* 侧边栏折叠面板 */
.side-fold {
    background: rgba(255,255,255,.7);
    border: 2px solid #2b2b2b;
    border-radius: 14px; padding: 0; margin: 10px 0 4px; overflow: hidden;
    box-shadow: 3px 3px 0 rgba(43,43,43,.85);
}
.side-fold summary {
    cursor: pointer; padding: 11px 15px; list-style: none;
    font-size: .8rem; font-weight: 800; color: #6b4f2a;
    letter-spacing: .6px;
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    user-select: none; transition: background .15s;
}
.side-fold summary:hover { background: rgba(255,210,30,.25); }
.side-fold summary::-webkit-details-marker { display: none; }
.side-fold summary .fold-arrow { color: #a4752f; transition: transform .22s; font-size: .72rem; }
.side-fold[open] summary .fold-arrow { transform: rotate(180deg); }
.side-fold[open] summary { border-bottom: 2px dashed rgba(43,43,43,.18); }
.side-fold .fold-body { padding: 4px 13px 10px; animation: foldIn .22s ease; }
@keyframes foldIn { from { opacity:0; transform: translateY(-4px);} to { opacity:1; transform:none;} }

/* 侧边栏 st.expander（简介面板）亮色化 */
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(255,255,255,.7);
    border: 2px solid #2b2b2b;
    color: #4a3728; box-shadow: 3px 3px 0 rgba(43,43,43,.85);
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
    color: #6b4f2a !important; font-weight: 800; font-size: .8rem; letter-spacing: .6px;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { color: #b3541e !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] p,
section[data-testid="stSidebar"] [data-testid="stExpander"] label,
section[data-testid="stSidebar"] [data-testid="stExpander"] caption,
section[data-testid="stSidebar"] [data-testid="stExpander"] .stCaption {
    color: #6b4f2a; font-size: .78rem;
}
.intro-text {
    color: #6b4f2a; font-size: .8rem; line-height: 1.7;
    padding: 2px 2px 8px;
}

/* 侧边栏导航按钮 */
section[data-testid="stSidebar"] .stButton > button {
    width:100%; border-radius:12px; border:2px solid #2b2b2b;
    background:#fff; color:#2b1d0e;
    font-weight:800; font-size:.9rem; padding:10px 14px;
    box-shadow: 3px 3px 0 #2b2b2b; transition: all .12s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background:#ffd21e; color:#2b1d0e; transform: translate(-1px,-1px);
    box-shadow: 4px 4px 0 #2b2b2b;
}
section[data-testid="stSidebar"] .stButton > button:active {
    transform: translate(2px,2px); box-shadow: 1px 1px 0 #2b2b2b;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: #ff4d4d;
    border:2px solid #2b2b2b; color:#fff;
    box-shadow: 3px 3px 0 #2b2b2b;
}
section[data-testid="stSidebar"] .stTextInput input {
    background: #fff; color:#2b1d0e;
    border:2px solid #2b2b2b; border-radius:10px;
}
section[data-testid="stSidebar"] .stTextInput input:focus {
    border-color:#ff4d4d; box-shadow: 2px 2px 0 rgba(255,77,77,.6);
}

/* ============ 通用按钮（蜡笔漫画风） ============ */
.stButton > button {
    border-radius: 12px; border: 2px solid #2b2b2b;
    background: #ffffff; color: #2b1d0e;
    font-weight: 800; padding: 9px 18px;
    box-shadow: 3px 3px 0 #2b2b2b;
    transition: all .12s ease;
}
.stButton > button:hover {
    background: #ffd21e; color: #2b1d0e;
    transform: translate(-1px,-1px);
    box-shadow: 5px 5px 0 #2b2b2b;
}
.stButton > button:active {
    transform: translate(2px,2px); box-shadow: 1px 1px 0 #2b2b2b;
}
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
    background: #ff4d4d;
    border: 2px solid #2b2b2b; color: #fff;
    box-shadow: 3px 3px 0 #2b2b2b;
}
.stButton > button[kind="primary"]:hover {
    background: #ff6b3d; color:#fff;
    transform: translate(-1px,-1px); box-shadow: 5px 5px 0 #2b2b2b;
}

/* ============ 聊天 ============ */
[data-testid="stChatMessage"] {
    background: #ffffff;
    border: 2.5px solid #2b2b2b;
    border-radius: 18px;
    padding: 14px 18px;
    box-shadow: 4px 4px 0 rgba(43,43,43,.9);
    animation: fadeUp .35s ease;
}
@keyframes fadeUp { from { opacity:0; transform: translateY(10px);} to { opacity:1; transform:none;} }

[data-testid="stChatInput"] {
    background: transparent;
}
[data-testid="stChatInput"] form, .st-chat-input {
    border-radius: 16px; overflow: hidden;
    box-shadow: 4px 4px 0 rgba(43,43,43,.9);
    border: 2.5px solid #2b2b2b;
}
[data-testid="stChatInput"] textarea {
    background:#fff !important; color:#2b1d0e !important;
}

.chat-header {
    display:flex; align-items:center; gap:14px;
    padding: 4px 2px 14px; border-bottom:3px solid #2b2b2b; margin-bottom:14px;
}
.ch-logo { width:46px; height:46px; border-radius:50%; flex-shrink:0;
    background:#ffd21e; border:2.5px solid #2b2b2b;
    display:flex; align-items:center; justify-content:center; font-size:23px;
    box-shadow: 3px 3px 0 #2b2b2b; }
.ch-title { font-size:1.12rem; font-weight:800; color:#2b1d0e; line-height:1.3; }
.ch-sub { font-size:.76rem; color:#8a6a3b; }
.ch-tag { margin-left:auto; white-space:nowrap; }

/* 侧边栏折叠按钮（stSidebarCollapseButton 展开态 / stExpandSidebarButton 折叠态）统一移到左下角：
   避免与顶部固定导航条争抢左上角；同时隐藏右上角无用的 Deploy 按钮 */
[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"] {
    position: fixed !important;
    top: auto !important;
    bottom: 14px !important;
    left: 10px !important;
    right: auto !important;
    z-index: 999999 !important;
    background: #fff !important;
    border: 2px solid #2b2b2b !important;
    border-radius: 10px !important;
    box-shadow: 2px 2px 0 rgba(43,43,43,.5) !important;
}
[data-testid="stAppDeployButton"] { display: none !important; }

/* ============ Hero 欢迎区 ============ */
.hero { position:relative; text-align:center; padding: 5vh 12px 24px; overflow:hidden; }
.hero::before, .hero::after {
    content:""; position:absolute; border-radius:50%; z-index:0;
    pointer-events:none; }
.hero::before { width:260px; height:260px; top:-90px; right:6%;
    background: radial-gradient(circle, rgba(255,210,30,.45) 0%, rgba(255,210,30,0) 68%); }
.hero::after { width:200px; height:200px; bottom:-70px; left:4%;
    background: radial-gradient(circle, rgba(255,159,28,.3) 0%, rgba(255,159,28,0) 70%); }
.hero > * { position:relative; z-index:1; }
.hero-badge {
    display:inline-flex; gap:8px; align-items:center;
    background: #ffd21e; color:#2b1d0e;
    padding: 6px 18px; border-radius:999px; font-size:.82rem; font-weight:800;
    border:2px solid #2b2b2b;
    box-shadow: 3px 3px 0 #2b2b2b; margin-bottom:18px;
    letter-spacing:.3px;
}
.hero h1 { font-size:2.05rem; font-weight:800; color:#2b1d0e;
           line-height:1.4; margin:0 0 10px; letter-spacing:-.5px; }
.grad-text {
    background: linear-gradient(120deg,#ff4d4d 10%,#ff9f1c 55%,#ffd21e 90%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero p { color:#8a6a3b; font-size:.96rem; margin:0 auto 6px; max-width:560px; }
.hero-feats { display:flex; gap:22px; justify-content:center; margin-top:16px;
              color:#8a6a3b; font-size:.8rem; flex-wrap:wrap; }
.hero-feats span b { color:#b3541e; }
/* 主页数据亮点条 */
.hero-stats { display:flex; flex-wrap:wrap; gap:10px; justify-content:center;
              margin:10px 0 16px; }
.hero-stats span { background:#fff; border:2px solid #2b2b2b; border-radius:999px;
    padding:5px 14px; font-size:.82rem; font-weight:700; color:#2b1d0e;
    box-shadow:2px 2px 0 rgba(43,43,43,.5); }
.hero-stats b { color:#e8590c; }
/* 主页 AI 专家团队 */
.hero-team { text-align:center; margin:16px 0 6px; }
.ht-head { font-size:.8rem; font-weight:800; color:#8a6a3b; margin-bottom:8px; }
.ht-row { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; }
.ht-row span { background:#fff; border:2px solid #2b2b2b; border-radius:10px;
    padding:4px 10px; font-size:.78rem; font-weight:700; color:#2b1d0e;
    box-shadow:2px 2px 0 rgba(43,43,43,.4); }

/* 主页示例问题快捷入口 */
.hero-suggest { max-width:860px; margin:6px auto 0; text-align:center; }
.hs-head { font-size:.8rem; font-weight:800; color:#8a6a3b; margin:4px 0 10px; }
[data-testid="stHorizontalBlock"] button {
    border-radius:12px; border:2px solid #2b2b2b;
    background:#fff; color:#2b1d0e; font-weight:700; font-size:.84rem;
    padding:10px 14px; box-shadow:2px 2px 0 rgba(43,43,43,.55);
    transition: all .12s ease;
}
[data-testid="stHorizontalBlock"] button:hover {
    transform: translate(-1px,-1px); box-shadow:3px 3px 0 rgba(43,43,43,.55);
    background:#fff8e1; color:#b3541e; border-color:#2b2b2b;
}
[data-testid="stHorizontalBlock"] button:active {
    transform: translate(1px,1px); box-shadow:1px 1px 0 rgba(43,43,43,.55);
}

/* ============ 主页：功能亮点 / 三步上手 ============ */
.home-sec-title {
    text-align:center; font-size:.95rem; font-weight:800; color:#b3541e;
    margin: 22px 0 12px; letter-spacing:.5px;
}
.home-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:14px;
              max-width:980px; margin:0 auto; }
.home-card {
    background:#fff; border:2px solid #2b2b2b; border-radius:16px;
    padding:16px 14px; text-align:left; box-shadow:3px 3px 0 rgba(43,43,43,.8);
    transition: transform .12s ease;
}
.home-card:hover { transform: translate(-2px,-2px) rotate(-.4deg);
                   box-shadow:4px 4px 0 rgba(43,43,43,.8); }
.hc-icon { font-size:1.5rem; line-height:1; }
.hc-title { color:#2b1d0e; font-weight:800; font-size:.92rem; margin:9px 0 4px; }
.hc-desc { color:#8a6a3b; font-size:.76rem; line-height:1.5; }

.steps { display:grid; grid-template-columns:repeat(3,1fr); gap:14px;
         max-width:980px; margin:0 auto; }
.step {
    background:rgba(255,255,255,.85); border:2px dashed #2b2b2b; border-radius:16px;
    padding:15px 14px; text-align:center; box-shadow:3px 3px 0 rgba(43,43,43,.55);
}
.step-num {
    display:inline-flex; width:30px; height:30px; border-radius:50%;
    background:#ffd21e; border:2px solid #2b2b2b; color:#2b1d0e;
    align-items:center; justify-content:center; font-weight:800; font-size:.9rem;
    margin-bottom:8px; box-shadow:2px 2px 0 #2b2b2b;
}
.step-title { color:#2b1d0e; font-weight:800; font-size:.9rem; }
.step-desc { color:#8a6a3b; font-size:.76rem; line-height:1.5; margin-top:4px; }
@media (max-width: 900px) {
    .home-cards { grid-template-columns: repeat(2,1fr); }
    .steps { grid-template-columns: repeat(1,1fr); }
}

/* ============ 深度思考面板 ============ */
.think-box {
    background: #fff8e1;
    border: 2px solid #2b2b2b;
    border-left: 5px solid #ff9f1c;
    border-radius: 12px; margin: 4px 0 12px; padding: 0; overflow: hidden;
}
.think-box summary {
    cursor:pointer; padding: 9px 13px; font-size:.83rem; color:#6b4f2a;
    font-weight:800; list-style:none; user-select:none; transition: background .15s;
}
.think-box summary:hover { background: rgba(255,210,30,.3); }
.think-box summary::-webkit-details-marker { display:none; }
.think-box summary .arrow { float:right; color:#a4752f; transition: transform .22s; }
.think-box[open] summary .arrow { transform: rotate(180deg); }
.think-content {
    padding: 8px 15px 12px; font-size:.8rem; color:#6b4f2a; line-height:1.75;
    white-space:pre-wrap; word-break:break-word;
    max-height: 340px; overflow-y: auto;
    border-top:2px dashed rgba(43,43,43,.2);
}

/* 思考中实时动画 */
.thinking-live {
    display:flex; align-items:center; gap:10px;
    background: #fff3c4;
    border:2px solid #2b2b2b;
    border-radius:12px; padding:11px 15px; margin-bottom:10px;
    color:#b3541e; font-size:.87rem; font-weight:800;
    box-shadow: 3px 3px 0 rgba(43,43,43,.85);
}
.tl-dots { display:inline-flex; gap:4px; }
.tl-dots span { width:7px; height:7px; border-radius:50%; background:#ff4d4d;
                display:inline-block; animation: blink 1.15s infinite; }
.tl-dots span:nth-child(2){ animation-delay:.18s; }
.tl-dots span:nth-child(3){ animation-delay:.36s; }
@keyframes blink { 0%,80%,100%{opacity:.22;} 40%{opacity:1;} }

/* ============ Agent 徽章 / 状态 ============ */
.agent-pill {
    display:inline-flex; align-items:center; gap:8px;
    background:#fff; border:2px solid #2b2b2b; border-radius:999px;
    padding:7px 15px; font-size:.84rem; color:#2b1d0e; font-weight:700;
    box-shadow: 3px 3px 0 rgba(43,43,43,.85); margin-bottom:10px;
}
.agent-pill .pdot { width:9px; height:9px; border-radius:50%; background:#2ecc40;
                    border:1.5px solid #2b2b2b; animation: pulse 1.6s infinite; }
@keyframes pulse {
    0%   { box-shadow: 0 0 0 0 rgba(46,204,64,.45); }
    70%  { box-shadow: 0 0 0 8px rgba(46,204,64,0); }
    100% { box-shadow: 0 0 0 0 rgba(46,204,64,0); }
}

/* ============ 协作时间线 ============ */
.timeline { margin: 10px 0 4px; }
.tl-item { display:flex; gap:12px; position:relative; padding-bottom:16px; }
.tl-item::before { content:""; position:absolute; left:17px; top:40px; bottom:2px;
                   width:3px; background:#ffd21e; border-radius:2px; }
.tl-item:last-child { padding-bottom:2px; }
.tl-item:last-child::before { display:none; }
.tl-icon {
    width:36px; height:36px; flex-shrink:0; border-radius:50%;
    display:flex; align-items:center; justify-content:center; font-size:17px;
    background:#ffd21e;
    border:2px solid #2b2b2b;
    box-shadow: 2px 2px 0 #2b2b2b; z-index:1;
}
.tl-body { flex:1; min-width:0; padding-top:1px; }
.tl-title { font-weight:800; color:#2b1d0e; font-size:.88rem; }
.tl-reason { color:#8a6a3b; font-size:.78rem; margin-top:2px; line-height:1.5; }
.tl-think { margin-top:8px; }

/* ============ 指标卡（运营页） ============ */
.m-grid { display:grid; grid-template-columns: repeat(5, 1fr); gap:14px; margin:12px 0 8px; }
@media (max-width: 1000px) { .m-grid { grid-template-columns: repeat(2, 1fr); } }
.m-card {
    border-radius:16px; padding:18px 16px; color:#fff; position:relative;
    overflow:hidden;
    border:2.5px solid #2b2b2b;
    box-shadow: 4px 4px 0 rgba(43,43,43,.9);
}
.m-card::after { content:""; position:absolute; right:-22px; top:-22px;
                 width:96px; height:96px; border-radius:50%; background:rgba(255,255,255,.18); }
.m-icon { font-size:1.45rem; margin-bottom:8px; }
.m-val  { font-size:1.85rem; font-weight:800; line-height:1; letter-spacing:-.5px; }
.m-label{ font-size:.78rem; opacity:.95; margin-top:7px; font-weight:600; }

/* ============ Expander / 数据表 ============ */
[data-testid="stExpander"] {
    border:2px solid #2b2b2b; border-radius:14px; background:#fff;
    box-shadow: 3px 3px 0 rgba(43,43,43,.85); overflow:hidden;
    margin-bottom:8px;
}
[data-testid="stExpander"] summary { font-weight:800; color:#2b1d0e; }
[data-testid="stDataFrame"] { border:2px solid #2b2b2b; border-radius:12px; overflow:hidden; }

/* ============ 知识库 ============ */
.kb-zone {
    border:2.5px dashed #2b2b2b; border-radius:16px; padding:18px 16px;
    background: rgba(255,255,255,.8); transition: background .2s;
}
.kb-zone:hover { background: #fff8e1; }

/* ================================================================
   精致化增强 V2
   ================================================================ */

/* 用户消息：蜡笔天蓝底 + 白字（小新风蓝天），与助手白卡形成对话感 */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #5db8ff;
    border: 2.5px solid #2b2b2b;
    box-shadow: 4px 4px 0 rgba(43,43,43,.9);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) li,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) span {
    color: #ffffff;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) strong,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) b {
    color: #ffffff;
}

/* 头像圆形 + 蜡笔描边 */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    border-radius: 50% !important;
    border: 2px solid #2b2b2b !important;
    box-shadow: 2px 2px 0 rgba(43,43,43,.85);
}

/* 输入框聚焦：黄色蜡笔高亮 */
[data-testid="stChatInput"]:focus-within form,
.st-chat-input:focus-within {
    border-color: #ff4d4d;
    box-shadow: 4px 4px 0 rgba(255,77,77,.7);
}

/* Spinner 蜡笔红 */
.stSpinner > div {
    border-color: rgba(255,77,77,.3) transparent rgba(255,77,77,.3) transparent !important;
}

/* 二级标题：红黄蜡笔装饰条 */
.stApp h2 {
    padding-left: 12px;
    border-left: 5px solid;
    border-image: linear-gradient(180deg,#ff4d4d,#ffd21e) 1;
    margin-top: 1.6rem;
}

/* Hero 装饰光斑（红黄蜡笔氛围） */
.hero { position: relative; overflow: hidden; }
.hero::before {
    content: ""; position: absolute; width: 360px; height: 360px;
    background: radial-gradient(circle, rgba(255,210,30,.28), transparent 70%);
    top: -130px; right: -90px; border-radius: 50%; pointer-events: none;
}
.hero::after {
    content: ""; position: absolute; width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(255,77,77,.14), transparent 70%);
    bottom: -110px; left: -70px; border-radius: 50%; pointer-events: none;
}

/* 回答中的 Markdown 表格：蜡笔卡片化 */
.stApp table {
    border-collapse: collapse; width: 100%;
    background: #fff;
    border: 2px solid #2b2b2b;
    box-shadow: 3px 3px 0 rgba(43,43,43,.85);
    font-size: .87rem;
    border-radius: 10px; overflow: hidden;
    margin: 10px 0;
}
.stApp th {
    background: #ffd21e; color: #2b1d0e;
    font-weight: 800; padding: 9px 13px; border: 2px solid #2b2b2b;
}
.stApp td { padding: 8px 13px; border: 1.5px dashed rgba(43,43,43,.3); color: #4a3728; }
.stApp tr:hover td { background: #fff8e1; }

/* 回答中的代码块与引用块 */
.stApp pre { border-radius: 12px; border: 2px solid #2b2b2b; }
.stApp blockquote {
    border-left: 5px solid #ff9f1c;
    background: #fff8e1;
    padding: 8px 14px; border-radius: 0 10px 10px 0;
    color: #6b4f2a; margin: 8px 0;
}

/* Expander 展开动画 */
[data-testid="stExpander"][open] { animation: fadeUp .25s ease; }

/* 分隔线柔化 */
.stApp hr { border-color: #e4ebf4; margin: 1.1rem 0; }

/* 消息操作栏：下载按钮迷你化 */
[data-testid="stDownloadButton"] > button {
    padding: 2px 12px !important; font-size: .78rem !important;
    border-radius: 9px !important; box-shadow: none !important; margin-top: 2px;
}
[data-testid="stDownloadButton"] > button:hover {
    box-shadow: 3px 3px 0 #2b2b2b !important; transform: translate(-1px,-1px) !important;
    background: #ffd21e;
}

/* 侧边栏历史会话按钮：紧凑单行 */
section[data-testid="stSidebar"] .hist-btn .stButton > button {
    padding: 6px 10px !important; font-size: .78rem !important;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    display: block;
}
.hist-item { font-size:.68rem; color:#8a6a3b; padding: 1px 4px 4px; }
.hist-active {
    background: #ff4d4d; border:2px solid #2b2b2b !important; color:#fff;
}

/* ============ 移动端适配（手机 / 窄屏） ============ */
@media (max-width: 768px) {
    /* 页面容器：撑满宽度、缩小边距 */
    .block-container { padding: 0.5rem 0.7rem 5.5rem !important; max-width: 100%; }

    /* Hero 欢迎区：标题与留白紧凑化 */
    .hero { padding: 18px 4px 12px; }
    .hero h1 { font-size: 1.45rem; line-height: 1.4; }
    .hero p { font-size: .86rem; }
    .hero-badge { font-size: .68rem; padding: 4px 11px; }
    .hero-feats { flex-wrap: wrap; gap: 8px 14px; font-size: .76rem; }

    /* 聊天区头部：副标题隐藏、标签换行 */
    .chat-header { flex-wrap: wrap; gap: 6px 10px; padding: 11px 13px; }
    .ch-sub { display: none; }
    .ch-tag { margin-left: 0; }
    .ch-logo { width: 36px; height: 36px; font-size: 19px; }
    .ch-title { font-size: .98rem; }

    /* 消息气泡与思考面板：紧凑 */
    [data-testid="stChatMessage"] { padding: 10px 12px; border-radius: 14px; }
    .think-box summary { font-size: .74rem; padding: 8px 10px; }
    .think-content { font-size: .8rem; }
    .tl-title { font-size: .82rem; }
    .tl-reason { font-size: .78rem; }

    /* 消息操作栏按钮缩小 */
    [data-testid="stDownloadButton"] > button {
        font-size: .7rem !important; padding: 2px 8px !important;
    }

    /* 通用按钮：更容易点按 */
    .stButton > button { padding: 8px 14px; font-size: .88rem; }

    /* 运营统计卡：紧凑两列 */
    .m-grid { gap: 9px; }
    .m-card { padding: 11px 9px; border-radius: 13px; }
    .m-icon { font-size: 1.25rem; }
    .m-val { font-size: 1.18rem; }
    .m-label { font-size: .63rem; }

    /* 知识库上传区 */
    .kb-zone { padding: 11px; }
}
</style>""", unsafe_allow_html=True)


# ======================================================================
# API 封装
# ======================================================================
def api_get(path: str, timeout: int = 10):
    try:
        r = requests.get(f"{API}{path}", timeout=timeout)
        if r.status_code == 200:
            return r.json()
        st.warning(f"接口异常 {r.status_code}: {r.text[:200]}")
    except Exception as e:
        st.warning(f"请求失败: {e}")
    return None


def api_post(path: str, payload: dict, timeout: int = 10):
    """POST 请求，自动附带登录 token；返回 (status_code, data)"""
    headers = {}
    token = st.session_state.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(f"{API}{path}", json=payload, headers=headers, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = {"detail": r.text[:300]}
        return r.status_code, data
    except Exception as e:
        return None, {"detail": str(e)}


@st.cache_data(ttl=30, show_spinner=False)
def _cached_health():
    """后端健康状态（缓存 30 秒：避免每次 rerun 同步等后端往返拖慢首屏）"""
    try:
        return requests.get(f"{API}/health", timeout=1.5).json()
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def _cached_agents():
    """专家团队配置（静态数据；失败返回 None 也会被短暂缓存，ttl 保持较短以便自动恢复）"""
    try:
        r = requests.get(f"{API}/api/agents", timeout=3)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def sse_chat(message: str, session_id: str | None):
    """消费 SSE 流式接口，逐条产出事件"""
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    with requests.post(f"{API}/api/chat/stream", json=payload, stream=True, timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                yield json.loads(line[6:])


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


# ======================================================================
# HTML 组件
# ======================================================================
def thinking_box(content: str, seconds, label: str = "已深度思考") -> str:
    sec = f"（用时 {seconds} 秒）" if seconds else ""
    return (f'<details class="think-box"><summary>🧠 {label}{sec}'
            f'<span class="arrow">▾</span></summary>'
            f'<div class="think-content">{esc(content)}</div></details>')


def trace_html(trace: list, thinkings: dict) -> str:
    """Agent 协作时间线（可内嵌各专家思维链）"""
    if not trace:
        return ""
    items = []
    for t in trace:
        agent = t.get("agent", "")
        icon, title, _ = TEAM.get(agent, ("🤖", agent, "#64748b"))
        reason = esc(t.get("reason", ""))
        think_html = ""
        th = (thinkings or {}).get(agent)
        if th and th.get("content"):
            think_html = (f'<details class="think-box tl-think"><summary>'
                          f'🧠 思维链 · {th.get("seconds", 0)} 秒'
                          f'<span class="arrow">▾</span></summary>'
                          f'<div class="think-content">{esc(th["content"])}</div></details>')
        reason_html = f'<div class="tl-reason">{reason}</div>' if reason else ""
        items.append(
            f'<div class="tl-item"><div class="tl-icon">{icon}</div>'
            f'<div class="tl-body"><div class="tl-title">{title}</div>'
            f'{reason_html}{think_html}</div></div>')
    return f'<div class="timeline">{"".join(items)}</div>'


# ======================================================================
# 行程日程卡：检测"第X天/Day X"结构并按天渲染
# ======================================================================
_DAY_TITLE = re.compile(
    r'(?m)^(?:#{1,3}\s*)?\**\s*(第\s*[0-9一二三四五六七八九十]+\s*[天日]|DAY\s*\d+|D\s*\d+)\**[\s::：]*[^\n]*$',
    re.IGNORECASE)


def _split_itinerary(content: str):
    """若回答含 ≥2 个'第X天/Day X'标题，返回 (引言, [(天标题, 当天内容)])，否则 None"""
    matches = list(_DAY_TITLE.finditer(content))
    if len(matches) < 2:
        return None
    intro = content[:matches[0].start()]
    days = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        title = m.group(0).lstrip("#").strip().strip("*").strip()[:22]
        body = content[m.end():end].strip()
        days.append((title or f"第{i + 1}天", body))
    return intro, days


def render_answer_block(msg: dict):
    """渲染一条助手消息：思考面板 + 正文（日程卡/普通）+ 协作时间线"""
    if msg.get("final_thinking"):
        st.markdown(thinking_box(msg["final_thinking"], msg.get("final_seconds", 0)),
                    unsafe_allow_html=True)
    content = msg.get("content", "")
    itinerary = _split_itinerary(content) if content else None
    if itinerary:
        intro, days = itinerary
        if intro.strip():
            st.markdown(intro)
        tabs = st.tabs([f"📍 {t}" for t, _ in days])
        for tab, (_, body) in zip(tabs, days):
            with tab:
                st.markdown(body if body.strip() else "_当天安排详见上文_")
    else:
        st.markdown(content)
    trace, thinkings = msg.get("trace") or [], msg.get("thinkings") or {}
    if trace:
        elapsed = msg.get("elapsed_ms")
        head = f"🔍 Agent 协作过程 · {len(trace)} 步"
        if elapsed:
            head += f" · 总耗时 {elapsed / 1000:.1f}s"
        with st.expander(head):
            st.markdown(trace_html(trace, thinkings), unsafe_allow_html=True)


def _export_md(msg: dict) -> str:
    """把一条助手回答导出为 Markdown 攻略文档"""
    parts = ["# 📖 AI 旅行规划 · 攻略文档\n"]
    if msg.get("final_thinking"):
        parts.append("> 由 DeepSeek 深度思考生成，多 Agent 专业团队协作\n")
    parts.append(msg.get("content", ""))
    trace = msg.get("trace") or []
    if trace:
        parts.append("\n---\n## 🤝 Agent 协作过程\n")
        for t in trace:
            icon, title, _ = TEAM.get(t.get("agent", ""), ("🤖", t.get("agent", ""), ""))
            reason = t.get("reason", "")
            parts.append(f"- {icon} **{title}**" + (f"：{reason}" if reason else ""))
    parts.append(f"\n---\n*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} · 旅游智能助手*")
    return "\n".join(parts)


def _assistant_index(msg_list_idx: int) -> int:
    """计算某条消息在前端列表中的位置对应会话内第几条助手消息"""
    return sum(1 for m in st.session_state.messages[:msg_list_idx]
               if m["role"] == "assistant")


def _send_feedback(msg_list_idx: int, rating: str):
    """提交点赞/点踩到后端"""
    sid = st.session_state.session_id
    if not sid:
        st.toast("会话未同步，暂时无法反馈", icon="⚠️")
        return
    try:
        r = requests.post(f"{API}/api/chat/feedback", timeout=10,
                          json={"session_id": sid,
                                "message_index": _assistant_index(msg_list_idx),
                                "rating": rating})
        if r.status_code == 200:
            st.session_state.feedbacks[msg_list_idx] = rating
            st.toast("感谢你的反馈！", icon="💖" if rating == "like" else "📝")
            st.rerun()
        else:
            st.toast(f"反馈失败: {r.text[:80]}", icon="⚠️")
    except Exception as e:
        st.toast(f"反馈失败: {e}", icon="⚠️")


def _send_favorite(msg_list_idx: int):
    """收藏一条助手回答到后端收藏夹"""
    msg = st.session_state.messages[msg_list_idx]
    content = msg.get("content", "")
    title = content.split("\n")[0].lstrip("#* ").strip()[:30] or "旅行攻略"
    sid = st.session_state.session_id or ""
    try:
        r = requests.post(f"{API}/api/favorites", timeout=10,
                          json={"title": title, "content": content, "session_id": sid})
        if r.status_code == 200:
            st.session_state.favorited[msg_list_idx] = True
            st.toast("已加入收藏夹 ⭐", icon="⭐")
            st.rerun()
        else:
            st.toast(f"收藏失败: {r.text[:80]}", icon="⚠️")
    except Exception as e:
        st.toast(f"收藏失败: {e}", icon="⚠️")


def _tts_audio(text: str):
    """用 edge-tts 生成朗读音频（截取前 600 字避免等待过长）"""
    import asyncio
    import io

    import edge_tts

    async def _gen():
        com = edge_tts.Communicate(text[:600], "zh-CN-XiaoyiNeural")
        buf = io.BytesIO()
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()

    return asyncio.run(_gen())


def answer_actions(msg: dict, idx: int):
    """助手消息操作栏：导出 Markdown / 点赞 / 点踩 / 收藏 / 朗读"""
    content = msg.get("content", "")
    if not content or content.startswith("⚠️"):
        return
    rated = st.session_state.feedbacks.get(idx)
    faved = st.session_state.favorited.get(idx)
    c1, c2, c3, c4, c5, _ = st.columns([0.62, 0.5, 0.5, 0.55, 0.62, 3.2])
    with c1:
        st.download_button(
            "📥 导出", data=_export_md(msg).encode("utf-8"),
            file_name=f"旅行攻略_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown", key=f"dl_{idx}", use_container_width=True,
            help="下载本条回答为 Markdown 攻略文档")
    with c2:
        if st.button("👍" if rated != "like" else "✅",
                     key=f"like_{idx}", disabled=rated is not None,
                     use_container_width=True, help="这条回答有帮助"):
            _send_feedback(idx, "like")
    with c3:
        if st.button("👎" if rated != "dislike" else "🚫",
                     key=f"dislike_{idx}", disabled=rated is not None,
                     use_container_width=True, help="这条回答需要改进"):
            _send_feedback(idx, "dislike")
    with c4:
        if st.button("⭐" if not faved else "🌟",
                     key=f"fav_{idx}", disabled=bool(faved),
                     use_container_width=True, help="收藏到我的收藏夹"):
            _send_favorite(idx)
    with c5:
        if st.button("🔊", key=f"tts_{idx}", use_container_width=True,
                     help="AI 朗读本条回答（前 600 字）"):
            st.session_state.tts_idx = idx
            st.rerun()
    if st.session_state.get("tts_idx") == idx:
        with st.spinner("正在准备朗读…"):
            try:
                audio = _tts_audio(re.sub(r"[#*`>\-|]", "", content))
            except Exception as e:
                st.toast(f"朗读生成失败: {e}", icon="⚠️")
                st.session_state.tts_idx = None
                st.rerun()
                return
        if audio:
            st.audio(audio, format="audio/mp3")
            if st.button("⏹️ 收起朗读", key=f"ttsstop_{idx}"):
                st.session_state.tts_idx = None
                st.rerun()


def _load_session(sid: str):
    """从后端加载历史会话到聊天区，并恢复 session_id 以继续对话"""
    detail = api_get(f"/api/admin/sessions/{sid}")
    if not detail:
        st.toast("加载会话失败", icon="⚠️")
        return
    msgs = []
    for m in detail.get("messages", []):
        if m.get("role") == "user":
            msgs.append({"role": "user", "content": m["content"]})
        else:
            msgs.append({"role": "assistant", "content": m["content"],
                         "trace": [], "thinkings": {}})
    st.session_state.messages = msgs
    st.session_state.session_id = sid
    st.session_state.pending = None
    st.session_state.feedbacks = {}
    st.rerun()


def typewriter_render(box, text: str, chunk_secs: float = 0.05):
    """打字机效果：按段落逐块渲染最终回答"""
    import time as _time
    chunks = [c for c in text.split("\n\n") if c.strip()]
    if len(chunks) <= 1:
        box.markdown(text)
        return
    buf = ""
    for i, c in enumerate(chunks):
        buf += c + "\n\n"
        box.markdown(buf + ("▍" if i < len(chunks) - 1 else ""))
        if i < len(chunks) - 1:
            _time.sleep(chunk_secs)


def metric_card(icon: str, value, label: str, bg: str) -> str:
    return (f'<div class="m-card" style="background:{bg}">'
            f'<div class="m-icon">{icon}</div><div class="m-val">{value}</div>'
            f'<div class="m-label">{label}</div></div>')


# ======================================================================
# 登录 / 注册
# ======================================================================
def render_auth():
    """未登录时渲染扇贝风格登录 / 注册卡片（组件回传表单，服务端鉴权）"""
    from components.auth_card import auth_card

    err = st.session_state.pop("auth_error", None)
    result = auth_card(error=err or "")

    if not result:
        return

    # 组件返回值在 session 内是“粘性”的（会跨 rerun 保留），用 nonce 去重，
    # 避免失败后 st.rerun 反复重放同一次提交造成死循环。
    nonce = result.get("nonce")
    if nonce and nonce == st.session_state.get("auth_nonce"):
        return
    st.session_state["auth_nonce"] = nonce

    mode = result.get("mode")
    username = (result.get("username") or "").strip()
    password = result.get("password") or ""

    if mode == "login":
        if not username or not password:
            st.session_state["auth_error"] = "请输入用户名和密码"
        else:
            code, data = api_post("/api/auth/login",
                                  {"username": username, "password": password})
            if code == 200:
                _set_auth(data)
                st.rerun()
            else:
                st.session_state["auth_error"] = data.get("detail", "登录失败")
    elif mode == "register":
        password2 = result.get("password2") or ""
        if not username or not password:
            st.session_state["auth_error"] = "请输入用户名和密码"
        elif password != password2:
            st.session_state["auth_error"] = "两次输入的密码不一致"
        else:
            code, data = api_post("/api/auth/register",
                                  {"username": username, "password": password})
            if code == 200:
                _set_auth(data)
                st.rerun()
            else:
                st.session_state["auth_error"] = data.get("detail", "注册失败")
    else:
        return

    st.rerun()


def _set_auth(data: dict):
    """登录 / 注册成功后写入会话状态"""
    st.session_state.auth_token = data.get("token")
    st.session_state.username = data.get("username")
    st.session_state.role = data.get("role")


# ======================================================================
# 侧边栏
# ======================================================================
def render_sidebar():
    global API  # 允许用户在侧边栏修改后端地址
    with st.sidebar:
        st.markdown(
            '<div class="brand"><div class="brand-logo">✈️</div>'
            '<div><div class="brand-name">旅游智能助手</div>'
            '<div class="brand-sub">AI 智能旅行规划</div></div></div>',
            unsafe_allow_html=True)

        # ===== 账号信息 / 修改密码 / 退出登录 =====
        if st.session_state.get("auth_token"):
            role_label = "管理员" if st.session_state.get("role") == "admin" else "普通用户"
            st.markdown(
                f'<div class="side-card"><div class="sc-title">当前账号</div>'
                f'<div class="side-row"><span>👤 {esc(st.session_state.get("username", ""))}</span>'
                f'<b style="color:#6ee7b7">{role_label}</b></div></div>',
                unsafe_allow_html=True)
            with st.expander("🔑 修改密码", expanded=False):
                with st.form("chpwd_form"):
                    old = st.text_input("旧密码", type="password", key="chpwd_old")
                    new = st.text_input("新密码", type="password", key="chpwd_new")
                    if st.form_submit_button("确认修改", use_container_width=True):
                        if not old or not new:
                            st.error("请填写旧密码和新密码")
                        else:
                            code, data = api_post("/api/auth/change-password",
                                                  {"old_password": old, "new_password": new})
                            if code == 200:
                                st.success("密码修改成功，下次登录请使用新密码")
                            else:
                                st.error(data.get("detail", "修改失败"))
            if st.button("🚪 退出登录", use_container_width=True):
                api_post("/api/auth/logout", {})
                for k in ("auth_token", "username", "role"):
                    st.session_state[k] = None
                st.session_state.page = "chat"
                st.rerun()
            st.markdown(
                '<div style="text-align:center;margin-top:6px">'
                '<a href="/app/static/index.html" target="_blank" '
                'style="font-size:.82rem;color:#8a7f6a;text-decoration:none">'
                '🌐 返回官网首页</a></div>',
                unsafe_allow_html=True)

        # ===== 历史会话（点击恢复并继续对话） =====
        with st.expander("🕘 历史会话", expanded=False):
            hist = api_get("/api/admin/sessions?limit=15") or []
            if not hist:
                st.caption("暂无历史会话")
            for s in hist:
                preview = (s.get("preview") or "新会话").replace("\n", " ")[:24]
                active = s["id"] == st.session_state.session_id
                tip = (f"{s['message_count']} 条消息 · 更新于 {_fmt_time(s['updated_at'])}"
                       + (" · 当前会话" if active else " · 点击恢复对话"))
                if st.button(("🟢 " if active else "💬 ") + preview,
                             key=f"hist_{s['id']}", use_container_width=True,
                             type="primary" if active else "secondary", help=tip):
                    _load_session(s["id"])

        # ===== 简介（系统状态 / Agent 团队 / 后端地址统一收纳，默认收起） =====
        with st.expander("📋 简介", expanded=False):
            st.markdown(
                '<div class="intro-text">✈️ 把一整支懂旅行的 AI 顾问团，装进口袋。<br/><br/>'
                '6 位专家各有所长——规划师把路线排得张弛有度，美食顾问带你钻进'
                '本地人才知道的巷子小店，分析师替你算清天气与预算。<br/><br/>'
                '每一次回答，DeepSeek 都会先深度思考、再落笔，'
                '所有建议都有真实攻略库背书。</div>'
                '<div style="color:#7dd3fc;font-size:.8rem;font-weight:700;'
                'text-align:right;padding:6px 2px 10px;font-style:italic;">'
                '—— 你只管出发，攻略交给他们</div>', unsafe_allow_html=True)

            # 系统状态（走缓存，避免阻塞首屏）
            health = _cached_health()
            if health:
                deepseek = "deepseek" in str(health.get("llm_provider", "")).lower()
                reasoner = "reasoner" in str(health.get("llm_model", "")).lower()
                badge = ('<div class="think-badge">🧠 DeepSeek 深度思考已启用</div>'
                         if deepseek and reasoner else "")
                st.markdown(
                    f'<div class="side-card"><div class="sc-title">系统状态</div>'
                    f'<div class="side-row"><span><span class="online-dot"></span>后端服务</span>'
                    f'<b style="color:#6ee7b7">在线</b></div>'
                    f'<div class="side-row"><span>AI 模型</span><b>{esc(health["llm_model"])}</b></div>'
                    f'<div class="side-row"><span>知识库</span>'
                    f'<b>{"✅ 就绪" if health["index_ready"] else "⚠️ 未构建"}</b></div>'
                    f'{badge}</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="side-card"><div class="sc-title">系统状态</div>'
                    '<div class="side-row"><span><span class="offline-dot"></span>后端服务</span>'
                    '<b style="color:#fca5a5">离线</b></div></div>', unsafe_allow_html=True)
                st.caption("启动后端：uvicorn app.main:app --port 8000")

            # Agent 团队（静态配置，走 10 分钟缓存）
            team = _cached_agents()
            if team:
                rows = []
                for e in team["experts"]:
                    rows.append(f'<div class="team-item"><div class="ti-icon">{e["icon"]}</div>'
                                f'<div><div class="ti-name">{esc(e["title"])}</div>'
                                f'<div class="ti-desc">{esc(e["description"])}</div></div></div>')
                sup = team["supervisor"]
                rows.append(f'<div class="team-item"><div class="ti-icon">{sup["icon"]}</div>'
                            f'<div><div class="ti-name">{esc(sup["title"])}</div>'
                            f'<div class="ti-desc">{esc(sup["description"])}</div></div></div>')
                n = len(team["experts"]) + 1
                st.markdown(
                    f'<div class="side-card"><div class="sc-title">Agent 团队 · {n} 位智能体</div>'
                    f'{"".join(rows)}</div>', unsafe_allow_html=True)

            # 后端地址（高级配置，沉底）
            API = st.text_input("后端地址", value=API, help="FastAPI 后端服务地址")


# ======================================================================
# 页面： 旅行咨询
# ======================================================================
def _render_nav_bar():
    """每页顶部导航条：所有页面间自由切换（紧凑横条，当前页彩色高亮）"""
    from components.feature_cards import feature_cards
    items = [
        {"key": "chat", "icon": "💬", "title": "旅行咨询",
         "color": "linear-gradient(135deg,#ff8a8a,#ff5252)"},
        {"key": "map", "icon": "🗺️", "title": "城市地图",
         "color": "linear-gradient(135deg,#6ec6ff,#3d9bff)"},
        {"key": "transit", "icon": "🚄", "title": "交通路线",
         "color": "linear-gradient(135deg,#5ee7a0,#20c997)"},
        {"key": "fav", "icon": "⭐", "title": "我的收藏",
         "color": "linear-gradient(135deg,#ffd21e,#ff9f1c)"},
        {"key": "features", "icon": "✨", "title": "产品功能",
         "color": "linear-gradient(135deg,#ffb38a,#ff7a59)"},
    ]
    if st.session_state.get("role") == "admin":  # 仅管理员可见运营 / 知识库入口
        items.append({"key": "admin", "icon": "📊", "title": "运营管理",
                      "color": "linear-gradient(135deg,#c39bff,#9d6bff)"})
        items.append({"key": "kb", "icon": "📚", "title": "知识库管理",
                      "color": "linear-gradient(135deg,#5db8ff,#2e9bff)"})
    sel = feature_cards(cards=items, key="nav_bar_top", layout="bar",
                        current=st.session_state.page, height=50)
    if sel and sel.get("page"):
        page = sel["page"]
        if st.session_state.page != page:
            st.session_state.page = page
            st.rerun()


def render_hero():
    user = esc(st.session_state.get("username") or "旅行家")
    st.markdown(
        '<div class="hero">'
        '<div class="hero-badge">🧠 DeepSeek 深度思考 · 多智能体协作</div>'
        f'<h1>你好，{user}，<span class="grad-text">想去哪儿？</span></h1>'
        '<p>一句话说出你的想法，AI 顾问团为你搞定行程 · 景点 · 交通 · 预算</p>'
        '<div class="hero-stats">'
        '<span>🤝 <b>6</b> 位 AI 专家</span><span>🌆 <b>20+</b> 热门城市</span>'
        '<span>📚 <b>真实</b> 攻略库</span><span>🧠 <b>思考</b> 全程可见</span>'
        '</div>'
        '<div class="hero-feats">'
        '<span>🗓️ <b>行程规划</b></span><span>🏛️ <b>景点攻略</b></span>'
        '<span>🍜 <b>美食探店</b></span><span>🌦️ <b>天气预算</b></span>'
        '</div>'
        '</div>', unsafe_allow_html=True)

    # 功能亮点：一应俱全的旅行能力（点击卡片直达对应功能页）
    st.markdown('<div class="home-sec-title">✨ 一应俱全的旅行能力</div>',
                unsafe_allow_html=True)
    fn_entries = [
        ("chat", "💬", "智能咨询", "多专家协作，深度思考后给你靠谱答案"),
        ("map", "🗺️", "城市地图", "高德地图一键加载，景点分布看全貌"),
        ("transit", "🚄", "交通路线", "跨城交通规划，怎么去怎么回都安排"),
        ("fav", "⭐", "我的收藏", "喜欢的攻略一键收藏，随时回看"),
        ("features", "✨", "产品功能", "完整功能介绍与最佳体验指南"),
    ]
    if st.session_state.get("role") == "admin":  # 管理员额外可见
        fn_entries += [
            ("admin", "📊", "运营管理", "使用数据与热门城市统计"),
            ("kb", "📚", "知识库管理", "攻略库的更新与维护"),
        ]
    fn_cols = 4
    for r in range(0, len(fn_entries), fn_cols):
        cols = st.columns(fn_cols)
        for i, (key, icon, title, desc) in enumerate(fn_entries[r:r + fn_cols]):
            with cols[i]:
                if st.button(f"{icon} {title}", key=f"home_fn_{key}",
                             use_container_width=True, help=desc):
                    st.session_state.page = key
                    st.rerun()

    # 三步上手
    st.markdown('<div class="home-sec-title">🚀 三步开启旅程</div>',
                unsafe_allow_html=True)
    steps = [
        ("1", "说出需求", "在下方输入框描述想去的地方、天数和预算"),
        ("2", "交给顾问", "调度中心派发专家，实时深度思考给出攻略"),
        ("3", "收藏出发", "满意就一键收藏，攻略随身带着走"),
    ]
    steps_html = "".join(
        f'<div class="step"><div class="step-num">{n}</div>'
        f'<div class="step-title">{t}</div><div class="step-desc">{d}</div></div>'
        for n, t, d in steps)
    st.markdown(f'<div class="steps">{steps_html}</div>', unsafe_allow_html=True)

    # 热门示例问题：点击即问，降低上手门槛
    st.markdown('<div class="home-sec-title">💡 不知道问什么？试试这些</div>',
                unsafe_allow_html=True)
    examples = [
        ("🗓️", "北京 3 天深度游", "帮我规划北京3天行程，预算3000元"),
        ("🍜", "成都美食之旅", "成都3天有哪些必吃的美食？"),
        ("🌦️", "西安天气与预算", "十一去西安天气怎么样，预算多少？"),
        ("🌟", "上海周末游", "上海2天怎么玩，有什么必打卡？"),
        ("🏝️", "三亚亲子度假", "带娃去三亚5天怎么安排，住哪里好？"),
        ("🏔️", "云南自由行", "云南7天自由行路线和花费大概多少？"),
    ]
    n_cols = 3
    for r in range(0, len(examples), n_cols):
        row = examples[r:r + n_cols]
        cols = st.columns(n_cols)
        for i, (icon, label, q) in enumerate(row):
            with cols[i]:
                if st.button(f"{icon} {label}", key=f"hero_ex_{r + i}",
                             use_container_width=True, help=q):
                    handle_prompt(q)


def handle_prompt(prompt: str):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        status = st.empty()
        status.markdown(
            '<div class="thinking-live"><span class="tl-dots"><span></span><span></span>'
            '<span></span></span>🧭 调度中心正在分析你的需求...</div>', unsafe_allow_html=True)
        answer_box = st.empty()

        answer, done_evt, error = "", None, None
        thinkings: dict = {}
        final_thinking, final_seconds = None, 0
        try:
            for evt in sse_chat(prompt, st.session_state.session_id):
                etype = evt.get("type")
                if etype == "route":
                    agent = evt.get("agent")
                    if agent == "FINISH":
                        status.markdown(
                            '<div class="thinking-live"><span class="tl-dots"><span></span>'
                            '<span></span><span></span></span>📝 团队汇总中，'
                            'AI 正在深度思考并整合所有专家的成果...</div>',
                            unsafe_allow_html=True)
                    else:
                        icon, title, _ = TEAM.get(agent, ("🤖", agent, "#64748b"))
                        reason = esc(evt.get("reason", ""))
                        status.markdown(
                            f'<div><div class="agent-pill"><span class="pdot"></span>{icon} '
                            f'{title} · 接手中</div>'
                            f'<div class="thinking-live"><span class="tl-dots"><span></span>'
                            f'<span></span><span></span></span>🧠 {title}正在深度思考...'
                            f'<span style="font-weight:400;color:#818cf8;font-size:.76rem">'
                            f'{reason}</span></div></div>', unsafe_allow_html=True)
                elif etype == "agent_thinking":
                    thinkings[evt["agent"]] = {"content": evt.get("content"),
                                               "seconds": evt.get("seconds", 0)}
                elif etype == "answer":
                    answer = evt.get("content", "")
                    final_thinking = evt.get("thinking")
                    final_seconds = evt.get("thinking_seconds", 0)
                elif etype == "done":
                    done_evt = evt
                elif etype == "error":
                    error = evt.get("message")
        except Exception as e:
            error = str(e)

        status.empty()
        if error:
            st.error(f"处理失败: {error}")
            st.session_state.messages.append(
                {"role": "assistant", "content": f"⚠️ 处理失败: {error}",
                 "trace": [], "thinkings": {}})
            return

        if done_evt:
            st.session_state.session_id = done_evt.get("session_id")

        msg = {"role": "assistant", "content": answer, "trace": (done_evt or {}).get("trace", []),
               "thinkings": thinkings, "final_thinking": final_thinking,
               "final_seconds": final_seconds,
               "elapsed_ms": (done_evt or {}).get("elapsed_ms", 0)}
        st.session_state.messages.append(msg)

        if final_thinking:
            st.markdown(thinking_box(final_thinking, final_seconds), unsafe_allow_html=True)
        typewriter_render(answer_box, answer)
        trace, elapsed = msg["trace"], msg["elapsed_ms"]
        if trace:
            head = f"🔍 Agent 协作过程 · {len(trace)} 步 · 总耗时 {elapsed / 1000:.1f}s"
            with st.expander(head):
                st.markdown(trace_html(trace, thinkings), unsafe_allow_html=True)
        answer_actions(msg, len(st.session_state.messages) - 1)


def page_chat():
    _render_nav_bar()
    if not st.session_state.messages:
        render_hero()
    else:
        hcol = st.columns([1, 0.18])
        with hcol[0]:
            st.markdown(
                '<div class="chat-header"><div class="ch-logo">🤖</div>'
                '<div><div class="ch-title">旅游智能助手</div>'
                '<div class="ch-sub">多 Agent 专业旅行团队 · 行程 / 景点 / 美食 / 数据分析</div></div>'
                '<div class="ch-tag"><span class="think-badge">🧠 DeepSeek 深度思考</span></div>'
                '</div>', unsafe_allow_html=True)
        with hcol[1]:
            if st.button("🗑 新对话", help="清空当前会话，开启全新咨询",
                         use_container_width=True):
                st.session_state.messages = []
                st.session_state.session_id = None
                st.session_state.pending = None
                st.session_state.feedbacks = {}
                st.rerun()

    # 历史消息
    for i, m in enumerate(st.session_state.messages):
        if m["role"] == "user":
            with st.chat_message("user", avatar="🧑"):
                st.markdown(m["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                render_answer_block(m)
                answer_actions(m, i)

    # 语音输入（浏览器语音识别，结果作为提问）
    try:
        from components.voice_input import voice_input
        voice = voice_input(key="voice_main")
        if voice and voice.get("text"):
            st.session_state.pending = voice["text"]
    except Exception:
        pass

    # 新消息：示例问题 or 输入框
    if st.session_state.get("pending"):
        prompt = st.session_state.pending
        st.session_state.pending = None
        handle_prompt(prompt)

    if prompt := st.chat_input("输入你的旅行需求，如：帮我规划北京3天行程，预算3000元"):
        handle_prompt(prompt)


# ======================================================================
# 页面： 运营管理
# ======================================================================
def page_admin():
    if st.session_state.get("role") != "admin":
        st.warning("无权访问：仅管理员可查看运营管理")
        return
    _render_nav_bar()
    st.markdown(
        '<div class="chat-header"><div class="ch-logo" style="background:linear-gradient(135deg,'
        '#ffd21e,#ff9f1c)">📊</div><div><div class="ch-title">运营管理</div>'
        '<div class="ch-sub">会话统计 · 专家调用分布 · 历史记录</div></div></div>',
        unsafe_allow_html=True)
    stats = api_get("/api/admin/stats")
    if stats is None:
        st.error("无法获取统计数据，请确认后端已启动")
        return

    likes, dislikes = stats.get("likes", 0), stats.get("dislikes", 0)
    total_fb = likes + dislikes
    if total_fb:
        rating_str = f"{likes / total_fb * 100:.0f}% 好评"
    else:
        rating_str = "暂无"
    cards = (
        metric_card("💬", stats["total_sessions"], "总会话数",
                    "linear-gradient(135deg,#5db8ff,#2e9bff)") +
        metric_card("✉️", stats["total_messages"], "总消息数",
                    "linear-gradient(135deg,#ff9f1c,#ff6b3d)") +
        metric_card("🤝", sum(stats["agent_calls"].values()), "专家调用总次数",
                    "linear-gradient(135deg,#ffd21e,#ff9f1c)") +
        metric_card("👍", rating_str, f"用户反馈 · 👍{likes} / 👎{dislikes}",
                    "linear-gradient(135deg,#ff4d4d,#ff6b6b)") +
        metric_card("📚", "就绪" if stats["index_ready"] else "未构建", "知识库索引",
                    "linear-gradient(135deg,#2ecc40,#27ae60)")
    )
    st.markdown(f'<div class="m-grid">{cards}</div>', unsafe_allow_html=True)
    st.caption(f"AI 引擎: {stats['llm_provider']} · {stats['llm_model']}")

    if stats["agent_calls"]:
        st.subheader("各专家调用分布")
        st.bar_chart(stats["agent_calls"], color="#0ea5e9", height=280)

    st.subheader("最近会话")
    sessions = api_get("/api/admin/sessions?limit=20") or []
    if not sessions:
        st.info("暂无会话记录，去聊天页发起第一个咨询吧")
        return
    for s in sessions:
        with st.expander(f"💬 {s['id']} · {s['message_count']} 条消息 · {_fmt_time(s['updated_at'])}"):
            detail = api_get(f"/api/admin/sessions/{s['id']}")
            if detail:
                for m in detail["messages"]:
                    role = "🧑 用户" if m["role"] == "user" else "🤖 助手"
                    st.markdown(f"**{role}** ({_fmt_time(m.get('ts', 0))}):")
                    st.text(m["content"][:600])


# ======================================================================
# 页面： 知识库管理
# ======================================================================
def page_kb():
    if st.session_state.get("role") != "admin":
        st.warning("无权访问：仅管理员可查看知识库管理")
        return
    _render_nav_bar()
    st.markdown(
        '<div class="chat-header"><div class="ch-logo" style="background:linear-gradient(135deg,'
        '#5db8ff,#2e9bff)">📚</div><div><div class="ch-title">知识库管理</div>'
        '<div class="ch-sub">攻略文档 · 向量索引 · RAG 检索底座</div></div></div>',
        unsafe_allow_html=True)
    docs = api_get("/api/knowledge/documents")
    if docs is None:
        st.error("无法连接后端")
        return

    st.subheader(f"文档列表（{len(docs)} 篇）")
    if docs:
        st.dataframe(
            [{"📄 文件名": d["name"], "大小 (KB)": round(d["size_bytes"] / 1024, 1),
              "修改时间": d["modified"]} for d in docs],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("知识库为空，请上传攻略文档")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="kb-zone">', unsafe_allow_html=True)
        st.subheader("⬆️ 上传攻略文档")
        st.caption("支持 .md / .txt，UTF-8 编码，单文件 ≤ 2MB")
        f = st.file_uploader("选择文件", type=["md", "txt"], label_visibility="collapsed")
        if st.button("上传文档", disabled=not f, type="primary", use_container_width=True):
            try:
                r = requests.post(f"{API}/api/knowledge/upload",
                                  files={"file": (f.name, f.getvalue())}, timeout=60)
                if r.status_code == 200:
                    st.success(r.json().get("message", "上传成功"))
                    st.rerun()
                else:
                    st.error(r.text[:200])
            except Exception as e:
                st.error(f"上传失败: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="kb-zone">', unsafe_allow_html=True)
        st.subheader("🔨 重建向量索引")
        st.caption("上传/删除文档后需重建索引才能生效（首次构建需下载 BGE 模型，耗时较长）")
        if st.button("立即重建", type="primary", use_container_width=True):
            with st.spinner("重建中，可能需要几分钟..."):
                try:
                    r = requests.post(f"{API}/api/knowledge/rebuild", timeout=1800)
                    if r.status_code == 200:
                        d = r.json()
                        st.success(f"完成: {d['documents']} 篇文档 / {d['chunks']} 个文本块 / "
                                   f"维度 {d['dimension']}")
                    else:
                        st.error(r.text[:300])
                except Exception as e:
                    st.error(f"重建失败: {e}")
        st.markdown('</div>', unsafe_allow_html=True)


# ======================================================================
# 城市景点地图（folium 交互地图）
# ======================================================================
CITY_GEO = {
    "北京": {
        "center": (39.9042, 116.4074),
        "spots": [
            ("天安门广场", 39.9087, 116.3975, "地标"),
            ("故宫博物院", 39.9163, 116.3972, "古迹"),
            ("景山公园", 39.9285, 116.3960, "公园"),
            ("南锣鼓巷", 39.9371, 116.4029, "街区"),
            ("雍和宫", 39.9477, 116.4175, "古迹"),
            ("北海公园", 39.9254, 116.3898, "公园"),
            ("天坛公园", 39.8822, 116.4066, "古迹"),
            ("颐和园", 39.9999, 116.2755, "公园"),
            ("圆明园", 40.0075, 116.3099, "古迹"),
            ("八达岭长城", 40.3587, 116.0169, "自然"),
        ],
    },
    "上海": {
        "center": (31.2304, 121.4737),
        "spots": [
            ("外滩", 31.2335, 121.4908, "地标"),
            ("南京路步行街", 31.2353, 121.4797, "街区"),
            ("豫园", 31.2273, 121.4922, "古迹"),
            ("东方明珠", 31.2397, 121.4998, "地标"),
            ("陆家嘴", 31.2397, 121.5010, "商圈"),
            ("田子坊", 31.2103, 121.4692, "街区"),
            ("武康路", 31.2050, 121.4374, "街区"),
            ("上海迪士尼", 31.1434, 121.6570, "乐园"),
        ],
    },
    "成都": {
        "center": (30.5728, 104.0668),
        "spots": [
            ("宽窄巷子", 30.6632, 104.0529, "街区"),
            ("人民公园", 30.6613, 104.0580, "公园"),
            ("武侯祠", 30.6459, 104.0487, "古迹"),
            ("锦里古街", 30.6447, 104.0489, "街区"),
            ("杜甫草堂", 30.6598, 104.0256, "古迹"),
            ("春熙路", 30.6602, 104.0817, "商圈"),
            ("大熊猫繁育基地", 30.7327, 104.1441, "亲子"),
            ("都江堰", 31.0049, 103.6107, "古迹"),
            ("青城山", 30.9020, 103.5804, "自然"),
        ],
    },
    "杭州": {
        "center": (30.2741, 120.1551),
        "spots": [
            ("西湖·断桥", 30.2591, 120.1498, "自然"),
            ("雷峰塔", 30.2122, 120.1490, "古迹"),
            ("河坊街", 30.2456, 120.1694, "街区"),
            ("灵隐寺", 30.2418, 120.1005, "古迹"),
            ("西溪湿地", 30.2609, 120.0629, "自然"),
            ("宋城", 30.1820, 120.1156, "乐园"),
            ("千岛湖", 29.6087, 118.9523, "自然"),
        ],
    },
    "西安": {
        "center": (34.3416, 108.9398),
        "spots": [
            ("钟楼", 34.2610, 108.9424, "地标"),
            ("回民街", 34.2650, 108.9402, "街区"),
            ("西安城墙", 34.2565, 108.9430, "古迹"),
            ("碑林博物馆", 34.2542, 108.9470, "古迹"),
            ("大雁塔", 34.2185, 108.9640, "古迹"),
            ("陕西历史博物馆", 34.2225, 108.9585, "场馆"),
            ("华清宫", 34.3620, 109.2120, "古迹"),
            ("秦始皇兵马俑", 34.3841, 109.2785, "古迹"),
        ],
    },
    "重庆": {
        "center": (29.5630, 106.5516),
        "spots": [
            ("解放碑", 29.5560, 106.5770, "商圈"),
            ("洪崖洞", 29.5630, 106.5780, "地标"),
            ("长江索道", 29.5580, 106.5850, "体验"),
            ("李子坝轻轨穿楼", 29.5600, 106.5280, "地标"),
            ("磁器口古镇", 29.5800, 106.4430, "街区"),
            ("南山一棵树观景台", 29.5500, 106.6300, "自然"),
            ("武隆天生三桥", 29.3220, 107.7580, "自然"),
        ],
    },
    "广州": {
        "center": (23.1291, 113.2644),
        "spots": [
            ("广州塔", 23.1066, 113.3245, "地标"),
            ("沙面岛", 23.1070, 113.2390, "街区"),
            ("陈家祠", 23.1180, 113.2450, "古迹"),
            ("越秀公园", 23.1450, 113.2620, "公园"),
            ("北京路步行街", 23.1280, 113.2670, "商圈"),
            ("珠江夜游天字码头", 23.1130, 113.2680, "体验"),
            ("白云山", 23.1880, 113.2990, "自然"),
            ("长隆野生动物世界", 22.9986, 113.3303, "乐园"),
        ],
    },
    "深圳": {
        "center": (22.5431, 114.0579),
        "spots": [
            ("世界之窗", 22.5340, 113.9740, "乐园"),
            ("深圳湾公园", 22.5230, 113.9480, "公园"),
            ("莲花山公园", 22.5580, 114.0560, "公园"),
            ("深圳博物馆", 22.5470, 114.0550, "场馆"),
            ("东门老街", 22.5470, 114.1190, "商圈"),
            ("甘坑客家小镇", 22.6390, 114.0940, "街区"),
            ("大梅沙海滨公园", 22.5890, 114.2500, "自然"),
        ],
    },
    "南京": {
        "center": (32.0603, 118.7969),
        "spots": [
            ("中山陵", 32.0570, 118.8470, "古迹"),
            ("明孝陵", 32.0550, 118.8380, "古迹"),
            ("夫子庙", 32.0210, 118.7850, "街区"),
            ("老门东", 32.0140, 118.7870, "街区"),
            ("总统府", 32.0470, 118.7970, "古迹"),
            ("玄武湖公园", 32.0720, 118.7940, "公园"),
            ("南京博物院", 32.0430, 118.8330, "场馆"),
            ("栖霞山", 32.1030, 118.8800, "自然"),
        ],
    },
    "武汉": {
        "center": (30.5928, 114.3055),
        "spots": [
            ("黄鹤楼", 30.5430, 114.3010, "古迹"),
            ("武汉长江大桥", 30.5490, 114.2880, "地标"),
            ("户部巷", 30.5430, 114.2880, "街区"),
            ("江汉路步行街", 30.5810, 114.2870, "商圈"),
            ("东湖", 30.5490, 114.3600, "自然"),
            ("武汉大学", 30.5390, 114.3650, "体验"),
            ("湖北省博物馆", 30.5620, 114.3660, "场馆"),
        ],
    },
    "长沙": {
        "center": (28.2282, 112.9388),
        "spots": [
            ("橘子洲", 28.1810, 112.9570, "地标"),
            ("岳麓山", 28.3350, 112.9330, "自然"),
            ("岳麓书院", 28.3200, 112.9370, "古迹"),
            ("太平街", 28.1940, 112.9760, "街区"),
            ("五一广场", 28.1940, 112.9770, "商圈"),
            ("天心阁", 28.1880, 112.9830, "古迹"),
            ("湖南博物院", 28.2210, 112.9860, "场馆"),
        ],
    },
    "三亚": {
        "center": (18.2528, 109.5119),
        "spots": [
            ("亚龙湾", 18.1970, 109.6370, "自然"),
            ("大东海", 18.2120, 109.5120, "自然"),
            ("三亚湾", 18.2260, 109.4580, "自然"),
            ("天涯海角", 18.2070, 109.2010, "自然"),
            ("蜈支洲岛", 18.3140, 109.7630, "自然"),
            ("南山文化旅游区", 18.2900, 109.2000, "古迹"),
            ("海棠湾免税城", 18.3470, 109.7330, "商圈"),
        ],
    },
    "昆明": {
        "center": (25.0389, 102.7183),
        "spots": [
            ("翠湖公园", 25.0490, 102.7060, "公园"),
            ("昆明老街", 25.0430, 102.7090, "街区"),
            ("金马碧鸡坊", 25.0370, 102.7070, "地标"),
            ("圆通寺", 25.0430, 102.7120, "古迹"),
            ("云南民族村", 24.9560, 102.6590, "体验"),
            ("滇池海埂公园", 24.9560, 102.6640, "自然"),
            ("西山龙门", 24.9550, 102.6290, "自然"),
        ],
    },
    "厦门": {
        "center": (24.4798, 118.0894),
        "spots": [
            ("鼓浪屿", 24.4480, 118.0670, "街区"),
            ("厦门大学", 24.4370, 118.0890, "体验"),
            ("南普陀寺", 24.4410, 118.0890, "古迹"),
            ("中山路步行街", 24.4570, 118.0840, "商圈"),
            ("沙坡尾", 24.4390, 118.0870, "街区"),
            ("曾厝垵", 24.4370, 118.1060, "街区"),
            ("环岛路", 24.4260, 118.1080, "自然"),
            ("厦门园林植物园", 24.4520, 118.0950, "公园"),
        ],
    },
    "天津": {
        "center": (39.0842, 117.2014),
        "spots": [
            ("天津之眼", 39.1548, 117.0716, "地标"),
            ("古文化街", 39.1480, 117.1860, "街区"),
            ("五大道", 39.1180, 117.2040, "街区"),
            ("意式风情区", 39.1530, 117.1930, "街区"),
            ("滨江道步行街", 39.1460, 117.1900, "商圈"),
            ("瓷房子", 39.1300, 117.1960, "场馆"),
        ],
    },
    "石家庄": {
        "center": (38.0428, 114.5149),
        "spots": [
            ("河北博物院", 38.0460, 114.5270, "场馆"),
            ("正定隆兴寺", 38.1470, 114.5700, "古迹"),
            ("赵州桥", 37.7350, 114.7620, "古迹"),
            ("正定古城墙", 38.1460, 114.5720, "古迹"),
            ("抱犊寨", 38.0520, 114.3250, "自然"),
        ],
    },
    "太原": {
        "center": (37.8706, 112.5489),
        "spots": [
            ("晋祠", 37.7060, 112.4350, "古迹"),
            ("山西博物院", 37.8730, 112.5380, "场馆"),
            ("太原古县城", 37.7870, 112.4850, "古迹"),
            ("食品街", 37.8680, 112.5610, "街区"),
            ("双塔寺", 37.8430, 112.5780, "古迹"),
        ],
    },
    "呼和浩特": {
        "center": (40.8424, 111.7490),
        "spots": [
            ("大召寺", 40.8000, 111.7330, "古迹"),
            ("内蒙古博物院", 40.8080, 111.6990, "场馆"),
            ("塞上老街", 40.8005, 111.7310, "街区"),
            ("席力图召", 40.7990, 111.7370, "古迹"),
            ("昭君博物院", 40.7100, 111.6720, "古迹"),
        ],
    },
    "沈阳": {
        "center": (41.8057, 123.4315),
        "spots": [
            ("沈阳故宫", 41.7960, 123.4550, "古迹"),
            ("张氏帅府", 41.7930, 123.4620, "古迹"),
            ("北陵公园", 41.8330, 123.4190, "公园"),
            ("中街", 41.7970, 123.4600, "街区"),
            ("九一八历史博物馆", 41.8120, 123.4280, "场馆"),
        ],
    },
    "大连": {
        "center": (38.9140, 121.6147),
        "spots": [
            ("星海广场", 38.8820, 121.5710, "地标"),
            ("老虎滩海洋公园", 38.8750, 121.6850, "乐园"),
            ("滨海路", 38.8880, 121.6320, "自然"),
            ("金石滩", 39.0220, 121.9570, "自然"),
            ("俄罗斯风情街", 38.9160, 121.6230, "街区"),
        ],
    },
    "长春": {
        "center": (43.8171, 125.3235),
        "spots": [
            ("伪满皇宫博物院", 43.8640, 125.3640, "古迹"),
            ("长影旧址博物馆", 43.8630, 125.2730, "场馆"),
            ("净月潭", 43.7860, 125.4330, "自然"),
            ("南湖公园", 43.8560, 125.3490, "公园"),
            ("长春世界雕塑园", 43.8140, 125.2870, "公园"),
        ],
    },
    "哈尔滨": {
        "center": (45.8038, 126.5350),
        "spots": [
            ("中央大街", 45.7690, 126.6210, "街区"),
            ("圣索菲亚大教堂", 45.7760, 126.6280, "古迹"),
            ("斯大林公园", 45.7790, 126.6100, "公园"),
            ("太阳岛", 45.7880, 126.5680, "自然"),
            ("哈尔滨大剧院", 45.8460, 126.5890, "场馆"),
            ("冰雪大世界", 45.7520, 126.6070, "乐园"),
        ],
    },
    "苏州": {
        "center": (31.2990, 120.5853),
        "spots": [
            ("拙政园", 31.3250, 120.6260, "古迹"),
            ("苏州博物馆", 31.3240, 120.6290, "场馆"),
            ("虎丘", 31.3220, 120.5720, "古迹"),
            ("平江路", 31.3170, 120.6330, "街区"),
            ("山塘街", 31.3180, 120.6010, "街区"),
            ("金鸡湖", 31.3210, 120.6680, "自然"),
            ("留园", 31.3170, 120.5980, "古迹"),
        ],
    },
    "无锡": {
        "center": (31.4912, 120.3119),
        "spots": [
            ("鼋头渚", 31.4290, 120.2140, "自然"),
            ("灵山大佛", 31.4180, 120.0920, "古迹"),
            ("拈花湾", 31.4380, 120.0430, "街区"),
            ("南长街", 31.5610, 120.3010, "街区"),
            ("惠山古镇", 31.5810, 120.2670, "古迹"),
        ],
    },
    "合肥": {
        "center": (31.8206, 117.2272),
        "spots": [
            ("三河古镇", 31.6880, 117.2720, "古迹"),
            ("包公园", 31.8430, 117.3090, "公园"),
            ("安徽博物院", 31.8290, 117.2220, "场馆"),
            ("逍遥津公园", 31.8690, 117.2850, "公园"),
            ("巢湖", 31.6000, 117.4800, "自然"),
        ],
    },
    "福州": {
        "center": (26.0745, 119.2965),
        "spots": [
            ("三坊七巷", 26.0870, 119.2950, "街区"),
            ("鼓山", 26.0560, 119.3850, "自然"),
            ("福州西湖公园", 26.0900, 119.2920, "公园"),
            ("烟台山", 26.0400, 119.3010, "街区"),
            ("上下杭", 26.0570, 119.3000, "街区"),
        ],
    },
    "南昌": {
        "center": (28.6820, 115.8579),
        "spots": [
            ("滕王阁", 28.6880, 115.8760, "古迹"),
            ("八一广场", 28.6780, 115.8940, "地标"),
            ("秋水广场", 28.6900, 115.8270, "地标"),
            ("八一起义纪念馆", 28.6790, 115.8840, "场馆"),
            ("万寿宫历史文化街区", 28.6760, 115.8790, "街区"),
        ],
    },
    "济南": {
        "center": (36.6512, 117.1201),
        "spots": [
            ("趵突泉", 36.6620, 117.0290, "自然"),
            ("大明湖", 36.6740, 117.0280, "公园"),
            ("千佛山", 36.6420, 117.0240, "自然"),
            ("芙蓉街", 36.6680, 117.0240, "街区"),
            ("山东博物馆", 36.6170, 117.1010, "场馆"),
        ],
    },
    "青岛": {
        "center": (36.0671, 120.3826),
        "spots": [
            ("栈桥", 36.0590, 120.3190, "地标"),
            ("八大关", 36.0540, 120.3510, "街区"),
            ("五四广场", 36.0620, 120.3830, "地标"),
            ("崂山", 36.1570, 120.6240, "自然"),
            ("青岛啤酒博物馆", 36.0770, 120.3650, "场馆"),
            ("浙江路天主教堂", 36.0670, 120.3210, "古迹"),
        ],
    },
    "郑州": {
        "center": (34.7466, 113.6254),
        "spots": [
            ("二七纪念塔", 34.7520, 113.6630, "地标"),
            ("河南博物院", 34.7930, 113.6830, "场馆"),
            ("少林寺", 34.5070, 112.9350, "古迹"),
            ("嵩山", 34.4860, 113.0390, "自然"),
            ("千玺广场", 34.7840, 113.7110, "地标"),
        ],
    },
    "洛阳": {
        "center": (34.6197, 112.4540),
        "spots": [
            ("龙门石窟", 34.5590, 112.4720, "古迹"),
            ("白马寺", 34.7300, 112.7700, "古迹"),
            ("洛阳博物馆", 34.6600, 112.4410, "场馆"),
            ("丽景门", 34.6820, 112.4610, "古迹"),
            ("老城十字街", 34.6810, 112.4590, "街区"),
            ("应天门", 34.6720, 112.4540, "古迹"),
        ],
    },
    "贵阳": {
        "center": (26.6477, 106.6302),
        "spots": [
            ("甲秀楼", 26.5730, 106.7240, "地标"),
            ("青岩古镇", 26.4940, 106.6760, "古迹"),
            ("黔灵山公园", 26.6170, 106.6750, "公园"),
            ("花溪公园", 26.4470, 106.6760, "公园"),
            ("贵州省博物馆", 26.6350, 106.6380, "场馆"),
        ],
    },
    "南宁": {
        "center": (22.8170, 108.3665),
        "spots": [
            ("青秀山", 22.7900, 108.3950, "自然"),
            ("南湖公园", 22.8140, 108.3390, "公园"),
            ("中山路美食街", 22.8130, 108.3210, "街区"),
            ("广西民族博物馆", 22.7740, 108.3880, "场馆"),
        ],
    },
    "桂林": {
        "center": (25.2742, 110.2902),
        "spots": [
            ("象鼻山", 25.2620, 110.2930, "自然"),
            ("两江四湖", 25.2760, 110.2880, "自然"),
            ("阳朔西街", 24.7730, 110.4880, "街区"),
            ("遇龙河", 24.8090, 110.4270, "自然"),
            ("芦笛岩", 25.3020, 110.2610, "自然"),
            ("龙脊梯田", 25.7350, 110.1040, "自然"),
        ],
    },
    "海口": {
        "center": (20.0444, 110.1999),
        "spots": [
            ("骑楼老街", 20.0300, 110.3330, "街区"),
            ("假日海滩", 20.0530, 110.2450, "自然"),
            ("海南省博物馆", 20.0130, 110.3430, "场馆"),
            ("万绿园", 20.0330, 110.3220, "公园"),
            ("火山口地质公园", 19.9270, 110.2240, "自然"),
        ],
    },
    "兰州": {
        "center": (36.0611, 103.8343),
        "spots": [
            ("中山桥", 36.0650, 103.8210, "地标"),
            ("白塔山公园", 36.0710, 103.8190, "公园"),
            ("甘肃省博物馆", 36.0750, 103.7770, "场馆"),
            ("黄河母亲雕塑", 36.0520, 103.8070, "地标"),
            ("正宁路夜市", 36.0530, 103.8310, "街区"),
        ],
    },
    "西宁": {
        "center": (36.6171, 101.7782),
        "spots": [
            ("塔尔寺", 36.4990, 101.5680, "古迹"),
            ("东关清真大寺", 36.6210, 101.7900, "古迹"),
            ("青海省博物馆", 36.6270, 101.7620, "场馆"),
            ("人民公园", 36.6280, 101.7570, "公园"),
        ],
    },
    "银川": {
        "center": (38.4872, 106.2309),
        "spots": [
            ("镇北堡西部影城", 38.4780, 105.9880, "体验"),
            ("西夏王陵", 38.4200, 105.9640, "古迹"),
            ("贺兰山岩画", 38.5330, 105.8860, "古迹"),
            ("南关清真大寺", 38.4720, 106.2410, "古迹"),
        ],
    },
    "拉萨": {
        "center": (29.6520, 91.1721),
        "spots": [
            ("布达拉宫", 29.6560, 91.1170, "古迹"),
            ("大昭寺", 29.6520, 91.1320, "古迹"),
            ("八廓街", 29.6530, 91.1340, "街区"),
            ("罗布林卡", 29.6460, 91.0990, "公园"),
            ("色拉寺", 29.6730, 91.1510, "古迹"),
            ("哲蚌寺", 29.6810, 91.0790, "古迹"),
        ],
    },
    "丽江": {
        "center": (26.8721, 100.2299),
        "spots": [
            ("丽江古城", 26.8770, 100.2340, "古迹"),
            ("玉龙雪山", 27.0170, 100.1900, "自然"),
            ("束河古镇", 26.9080, 100.2010, "古迹"),
            ("黑龙潭公园", 26.8920, 100.2340, "公园"),
            ("蓝月谷", 27.0040, 100.2050, "自然"),
            ("拉市海", 26.8900, 100.1060, "自然"),
        ],
    },
    "乌鲁木齐": {
        "center": (43.8256, 87.6168),
        "spots": [
            ("新疆国际大巴扎", 43.7870, 87.6240, "街区"),
            ("红山公园", 43.8070, 87.6020, "公园"),
            ("新疆博物馆", 43.7990, 87.5780, "场馆"),
            ("天山大峡谷", 43.4250, 87.8870, "自然"),
            ("水磨沟公园", 43.8330, 87.6540, "公园"),
        ],
    },
}


def _city_letter(city: str) -> str:
    """城市名拼音首字母（大写），用于按字母分组选择（重庆→C、厦门→X）"""
    if lazy_pinyin:
        return lazy_pinyin(city)[0][0].upper()
    return city[0].upper()


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两坐标球面直线距离（公里），用于城市间出行方式建议"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ======================================================================
# 高德地图（配置 AMAP_KEY 后启用；未配置时回退 folium）
# ======================================================================
AMAP_KEY = os.environ.get("AMAP_KEY", "").strip()
AMAP_SECURITY_JS_CODE = os.environ.get("AMAP_SECURITY_JS_CODE", "").strip()


def _wgs84_to_gcj02(lng: float, lat: float):
    """WGS-84 → GCJ-02（火星坐标系，高德使用），返回 (gcj_lng, gcj_lat)"""
    t_lng, t_lat = lng - 105.0, lat - 35.0
    dlat = (-100.0 + 2.0 * t_lng + 3.0 * t_lat + 0.2 * t_lat * t_lat
            + 0.1 * t_lng * t_lat + 0.2 * math.sqrt(abs(t_lng))
            + (20.0 * math.sin(6.0 * t_lng * math.pi)
               + 20.0 * math.sin(2.0 * t_lng * math.pi)) * 2.0 / 3.0
            + (20.0 * math.sin(t_lat * math.pi)
               + 40.0 * math.sin(t_lat / 3.0 * math.pi)) * 2.0 / 3.0
            + (160.0 * math.sin(t_lat / 12.0 * math.pi)
               + 320.0 * math.sin(t_lat * math.pi / 30.0)) * 2.0 / 3.0)
    dlng = (300.0 + t_lng + 2.0 * t_lat + 0.1 * t_lng * t_lng
            + 0.1 * t_lng * t_lat + 0.1 * math.sqrt(abs(t_lng))
            + (20.0 * math.sin(6.0 * t_lng * math.pi)
               + 20.0 * math.sin(2.0 * t_lng * math.pi)) * 2.0 / 3.0
            + (20.0 * math.sin(t_lng * math.pi)
               + 40.0 * math.sin(t_lng / 3.0 * math.pi)) * 2.0 / 3.0
            + (150.0 * math.sin(t_lng / 12.0 * math.pi)
               + 300.0 * math.sin(t_lng / 30.0 * math.pi)) * 2.0 / 3.0)
    radlat = lat / 180.0 * math.pi
    ee = 0.00669342162296594323
    magic = 1 - ee * math.sin(radlat) * math.sin(radlat)
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((6378245.0 * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (6378245.0 / sqrtmagic * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat


_AMAP_MAP_TPL = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html, body {margin:0; padding:0; font-family:"Yuanti SC","幼圆","Microsoft YaHei",sans-serif;}
  #am-tools {display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px;}
  .amt {border:2px solid #2b2b2b; border-radius:10px; background:#fff; color:#2b1d0e;
        font-weight:800; font-size:.82rem; padding:7px 14px; cursor:pointer;
        box-shadow:3px 3px 0 #2b2b2b; transition:all .12s;}
  .amt:hover {background:#ffd21e; transform:translate(-1px,-1px); box-shadow:4px 4px 0 #2b2b2b;}
  .amt:active {transform:translate(2px,2px); box-shadow:1px 1px 0 #2b2b2b;}
  .amt.on {background:#ff4d4d; color:#fff;}
  #am-map {width:100%; height:500px; border:2.5px solid #2b2b2b; border-radius:16px;
           box-shadow:4px 4px 0 rgba(43,43,43,.9);}
  .am-tip {font-size:.75rem; color:#8a6a3b; margin-top:7px; font-weight:600;}
  .amap-marker-label {border:2px solid #2b2b2b !important; border-radius:8px !important;
      padding:2px 7px !important; background:#fff9e0 !important; color:#2b1d0e !important;
      font-weight:700 !important; font-size:12px !important;
      box-shadow:2px 2px 0 rgba(43,43,43,.55) !important;}
</style>
</head>
<body>
<div id="am-tools">
  <button class="amt on" data-m="marks">&#128205; 景点标记</button>
  <button class="amt" data-m="driving">&#128663; 驾车路线</button>
  <button class="amt" data-m="walking">&#128694; 步行路线</button>
  <button class="amt" data-m="transit">&#128652; 公交路线</button>
</div>
<div id="am-map"></div>
<div class="am-tip">路线按推荐游玩顺序串联各景点 · 点击地图标记查看详情 · 滚轮缩放</div>
__SECURITY__
<script src="https://webapi.amap.com/maps?v=2.0&key=__KEY__"></script>
<script>
const DATA = __PAYLOAD__;
const map = new AMap.Map("am-map", {center: [DATA.center.lng, DATA.center.lat], zoom: 12});
map.setStatus({scrollWheel: true});
// Scale/ToolBar 在 JS API 2.0 是插件，必须 AMap.plugin 加载；包裹 try 避免阻断标记与路线主逻辑
AMap.plugin(["AMap.Scale", "AMap.ToolBar"], function() {
  try {
    map.addControl(new AMap.Scale());
    map.addControl(new AMap.ToolBar({position: "RT"}));
  } catch (e) { console.warn("控件加载失败:", e); }
});

const CAT_ICON = {"地标":"\\ud83c\\udfdb\\ufe0f","古迹":"\\ud83c\\udfdf\\ufe0f","公园":"\\ud83c\\udf33",
                  "街区":"\\ud83c\\udf92\\ufe0f","商圈":"\\ud83d\\udecd\\ufe0f","自然":"\\ud83c\\udf04",
                  "乐园":"\\ud83c\\udfa1","亲子":"\\ud83d\\udc3c","体验":"\\ud83d\\udea1","场馆":"\\ud83c\\udfa8"};

DATA.spots.forEach(function(s, i) {
  const mk = new AMap.Marker({
    position: [s.lng, s.lat],
    label: {content: (i + 1) + "." + s.name, direction: "right", offset: new AMap.Pixel(12, -6)}
  });
  mk.on("click", function() {
    const iw = new AMap.InfoWindow({
      content: '<div style="font-weight:800;font-size:14px">' + (i + 1) + '. ' + s.name + '</div>' +
               '<div style="color:#8a6a3b;font-size:12px;margin-top:3px">' +
               (CAT_ICON[s.cat] || "\\ud83d\\udccd") + ' ' + s.cat +
               ' \\u00b7 推荐顺序第 ' + (i + 1) + ' 站</div>',
      offset: new AMap.Pixel(0, -32)
    });
    iw.open(map, [s.lng, s.lat]);
  });
  map.add(mk);
});

let planners = [];
function clearRoutes() {
  planners.forEach(function(p) { try { p.clear(); } catch (e) {} });
  planners = [];
}
function planRoute(mode) {
  clearRoutes();
  if (mode === "marks") return;
  const plugin = mode === "driving" ? "AMap.Driving"
               : mode === "walking" ? "AMap.Walking" : "AMap.Transfer";
  AMap.plugin(plugin, function() {
    let idx = 0;
    const next = function() {
      if (idx >= DATA.spots.length - 1) return;
      const a = DATA.spots[idx], b = DATA.spots[idx + 1];
      let planner;
      if (mode === "transit") {
        planner = new AMap.Transfer({map: map, city: DATA.city, hideMarkers: true});
      } else if (mode === "driving") {
        planner = new AMap.Driving({map: map, hideMarkers: true});
      } else {
        planner = new AMap.Walking({map: map, hideMarkers: true});
      }
      planners.push(planner);
      planner.search(new AMap.LngLat(a.lng, a.lat), new AMap.LngLat(b.lng, b.lat),
        function() { idx += 1; setTimeout(next, 130); });
    };
    next();
  });
}
document.querySelectorAll(".amt").forEach(function(btn) {
  btn.addEventListener("click", function() {
    document.querySelectorAll(".amt").forEach(function(b) { b.classList.remove("on"); });
    btn.classList.add("on");
    planRoute(btn.dataset.m);
  });
});
</script>
</body>
</html>"""


# ===== 城市交通路线（跨城）：出发城市 → 到达城市 的驾车路线 =====
_AMAP_ROUTE_TPL = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { height: 100%; }
  #am-map { width: 100%; height: 100%; }
  #am-bar { position: absolute; top: 10px; left: 10px; z-index: 99;
      background: #fff9e0; border: 2px solid #2b2b2b; border-radius: 10px;
      padding: 8px 12px; font-size: 13px; font-weight: 700; color: #2b1d0e;
      box-shadow: 3px 3px 0 rgba(43,43,43,.55); max-width: 92%; }
  .amap-marker-label {border:2px solid #2b2b2b !important; border-radius:8px !important;
      padding:2px 7px !important; background:#fff9e0 !important; color:#2b1d0e !important;
      font-weight:700 !important; font-size:12px !important;
      box-shadow:2px 2px 0 rgba(43,43,43,.55) !important;}
</style>
</head>
<body>
<div id="am-map"></div>
<div id="am-bar">🚗 正在规划 __FROM__ → __TO__ 的驾车路线…</div>
__SECURITY__
<script src="https://webapi.amap.com/maps?v=2.0&key=__KEY__"></script>
<script>
const DATA = __PAYLOAD__;
const map = new AMap.Map("am-map", {zoom: 5});
map.setStatus({scrollWheel: true});
AMap.plugin(["AMap.Scale", "AMap.ToolBar"], function() {
  try {
    map.addControl(new AMap.Scale());
    map.addControl(new AMap.ToolBar({position: "RT"}));
  } catch (e) { console.warn("控件加载失败:", e); }
});
map.add([
  new AMap.Marker({position: [DATA.from.lng, DATA.from.lat],
    label: {content: "🚩 出发 · " + DATA.from.name, direction: "right",
            offset: new AMap.Pixel(12, -6)}}),
  new AMap.Marker({position: [DATA.to.lng, DATA.to.lat],
    label: {content: "🏁 到达 · " + DATA.to.name, direction: "right",
            offset: new AMap.Pixel(12, -6)}})
]);
map.setFitView();
AMap.plugin("AMap.Driving", function() {
  const dr = new AMap.Driving({map: map, hideMarkers: true});
  dr.search(new AMap.LngLat(DATA.from.lng, DATA.from.lat),
            new AMap.LngLat(DATA.to.lng, DATA.to.lat),
    function(status, result) {
      const bar = document.getElementById("am-bar");
      if (status === "complete" && result.routes && result.routes.length) {
        const r = result.routes[0];
        const km = (r.distance / 1000).toFixed(0);
        const h = Math.floor(r.duration / 3600);
        const m = Math.round((r.duration % 3600) / 60);
        bar.textContent = "🚗 " + DATA.from.name + " → " + DATA.to.name +
          " · 全程约 " + km + " 公里 · 驾车约 " +
          (h ? h + " 小时" + (m ? " " + m + " 分钟" : "") : m + " 分钟");
      } else {
        bar.textContent = "⚠️ 驾车路线规划失败，已标注两城位置（距离过远或超出规划范围）";
      }
    });
});
</script>
</body>
</html>"""


# ===== 个性化旅行需求解析（地图页：输入需求 → 智能筛选景点） =====
_TRAVEL_CAT_KEYS = {
    "地标": ("地标", "标志", "打卡", "著名", "必去", "网红"),
    "古迹": ("历史", "古迹", "古建筑", "文化", "寺庙", "文物", "古镇", "古街"),
    "公园": ("公园", "绿地", "园林", "散步"),
    "街区": ("街区", "胡同", "老街", "巷子", "逛街", "夜市"),
    "商圈": ("购物", "商圈", "商场", "买买买"),
    "自然": ("自然", "山水", "风景", "爬山", "山", "湖", "海", "江", "河", "草原", "海滩", "海边"),
    "乐园": ("乐园", "游乐园", "迪士尼", "环球", "欢乐谷", "刺激"),
    "亲子": ("孩子", "亲子", "儿童", "小孩", "遛娃", "家庭", "带娃", "宝宝", "熊猫", "动物园"),
    "体验": ("体验", "手工", "美食", "小吃", "温泉"),
    "场馆": ("场馆", "博物馆", "美术馆", "科技馆", "艺术", "展览", "剧院", "音乐"),
}
_CITY_ALIASES = {"帝都": "北京", "魔都": "上海", "羊城": "广州", "鹏城": "深圳",
                 "金陵": "南京", "江城": "武汉", "星城": "长沙", "春城": "昆明",
                 "鹭岛": "厦门", "鹿城": "三亚"}
_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_SPOT_SUFFIXES = ("广场", "公园", "博物院", "纪念馆", "古街", "步行街",
                  "基地", "中心", "寺", "山", "湖", "岛")


def _spot_short(name: str) -> str:
    """景点短名：剥掉通用后缀，支持"故宫"匹配"故宫博物院"（双字名不剥）"""
    for suf in _SPOT_SUFFIXES:
        if name.endswith(suf) and len(name) > len(suf) + 1:
            return name[:-len(suf)]
    return name


def _parse_travel_query(text: str):
    """解析旅行需求 → (城市, 偏好分类, 天数, 明确提到的景点列表)"""
    city = next((c for c in CITY_GEO if c in text), None)
    alias_hit = None
    if not city:
        for alias, name in _CITY_ALIASES.items():
            if alias in text:
                city, alias_hit = name, alias
                break
    # 剔除城市名后再匹配偏好，避免"上海"的"海"、"杭州"的"湖"误命中"自然"
    t = text.replace(city, "") if city else text
    if alias_hit:
        t = t.replace(alias_hit, "")
    cats = [c for c, keys in _TRAVEL_CAT_KEYS.items() if any(k in t for k in keys)]
    days = None
    m = re.search(r"(\d+|[一两二三四五六七八九十])\s*(?:天|日)", t)
    if m:
        g = m.group(1)
        days = _CN_NUM[g] if g in _CN_NUM else int(g)
    must = [s for s in CITY_GEO[city]["spots"]
            if s[0] in text or _spot_short(s[0]) in text] if city else []
    return city, cats, days, must


def _pick_spots(info: dict, cats: list, days, must: list):
    """按需求筛选景点：明确提到/偏好命中的全保留，不足按天数（每天3个）补齐"""
    spots = info["spots"]
    must_names = {s[0] for s in must}
    target = min((days or 3) * 3, len(spots))
    picked, matched = [], set()
    for s in spots:
        if s[0] in must_names or (cats and s[3] in cats):
            picked.append(s)
            matched.add(s[0])
    for s in spots:  # 数量不足时按推荐顺序补齐
        if len(picked) >= target:
            break
        if s not in picked:
            picked.append(s)
    return picked, matched


def _amap_map_html(key: str, security_js_code: str, city: str, info: dict) -> str:
    """生成高德地图页面：坐标转 GC-02 后注入 JS 组件"""
    clat, clng = info["center"]
    c_lng, c_lat = _wgs84_to_gcj02(clng, clat)
    spots = []
    for name, sla, slo, cat in info["spots"]:
        g_lng, g_lat = _wgs84_to_gcj02(slo, sla)
        spots.append({"name": name, "lng": round(g_lng, 6),
                      "lat": round(g_lat, 6), "cat": cat})
    payload = json.dumps({"city": city,
                          "center": {"lng": round(c_lng, 6), "lat": round(c_lat, 6)},
                          "spots": spots}, ensure_ascii=False)
    security = ('<script>window._AMapSecurityConfig = {securityJsCode: "'
                + security_js_code + '"};</script>') if security_js_code else ""
    return (_AMAP_MAP_TPL
            .replace("__KEY__", key)
            .replace("__SECURITY__", security)
            .replace("__PAYLOAD__", payload))


def _route_map_html(key: str, security_js_code: str, from_city: str, to_city: str) -> str:
    """生成跨城交通路线地图：起终点标记 + 高德驾车路线 + 距离时长信息条"""
    f_lat, f_lng = CITY_GEO[from_city]["center"]
    t_lat, t_lng = CITY_GEO[to_city]["center"]
    f_glng, f_glat = _wgs84_to_gcj02(f_lng, f_lat)
    t_glng, t_glat = _wgs84_to_gcj02(t_lng, t_lat)
    payload = json.dumps({
        "from": {"name": from_city, "lng": round(f_glng, 6), "lat": round(f_glat, 6)},
        "to": {"name": to_city, "lng": round(t_glng, 6), "lat": round(t_glat, 6)},
    }, ensure_ascii=False)
    security = ('<script>window._AMapSecurityConfig = {securityJsCode: "'
                + security_js_code + '"};</script>') if security_js_code else ""
    return (_AMAP_ROUTE_TPL
            .replace("__KEY__", key)
            .replace("__SECURITY__", security)
            .replace("__FROM__", from_city)
            .replace("__TO__", to_city)
            .replace("__PAYLOAD__", payload))


def page_map():
    _render_nav_bar()

    st.markdown(
        '<div class="chat-header"><div class="ch-logo" style="background:linear-gradient(135deg,'
        '#2ecc40,#27ae60)">🗺️</div><div><div class="ch-title">城市景点地图</div>'
        f'<div class="ch-sub">{len(CITY_GEO)} 城 · 覆盖全国主要城市 · 景点分布 · 推荐游玩路线</div></div></div>',
        unsafe_allow_html=True)

    # 按拼音首字母分组选择城市（两级下拉：字母 → 该字母下的城市）
    if lazy_pinyin:
        letters = sorted({_city_letter(c) for c in CITY_GEO})
        lcol, ccol = st.columns([1, 3])
        with lcol:
            letter = st.selectbox("拼音首字母", letters, key="city_letter")
        with ccol:
            cities = [c for c in CITY_GEO if _city_letter(c) == letter]
            city = st.selectbox("选择城市", cities, key="city_pick")
    else:
        city = st.selectbox("选择城市", list(CITY_GEO.keys()))
    info = CITY_GEO[city]

    # 个性化需求：输入后回车，智能筛选景点并联动地图/路线
    query = st.text_input(
        "✍️ 输入你的旅行需求（可选）",
        placeholder="例如：北京三日游，喜欢历史古迹，带孩子 —— 输入后按回车生效",
        key="map_query")
    matched = None
    if query.strip():
        p_city, cats, days, must = _parse_travel_query(query.strip())
        if p_city:
            city = p_city
            spots, matched = _pick_spots(CITY_GEO[city], cats, days, must)
            info = {"center": CITY_GEO[city]["center"], "spots": spots}
            bits = [f"📍 {city}"]
            if days:
                bits.append(f"约 {days} 天")
            if cats:
                bits.append("偏好 " + "/".join(cats))
            bits.append(f"筛选出 {len(spots)} 个景点")
            st.success(" · ".join(bits))
        else:
            st.warning("未能识别城市：请在需求中包含城市名（如“北京三日游”），暂按上方选择的城市展示。")

    left, right = st.columns([3, 2])
    with left:
        if AMAP_KEY:  # 高德地图：中文底图 + 真实路线规划
            components.html(_amap_map_html(AMAP_KEY, AMAP_SECURITY_JS_CODE, city, info),
                            height=590, scrolling=False)
        else:  # 回退 folium
            try:
                import folium
                from streamlit_folium import st_folium
            except ImportError:
                st.info("地图组件加载中（依赖未安装）：请运行 pip install folium streamlit-folium")
            else:
                lat, lon = info["center"]
                m = folium.Map(location=[lat, lon], zoom_start=12,
                               tiles="OpenStreetMap", control_scale=True)
                points = []
                for name, sla, slo, cat in info["spots"]:
                    points.append((sla, slo))
                    folium.Marker(
                        [sla, slo], popup=f"<b>{name}</b><br>{cat}",
                        tooltip=f"{name} · {cat}",
                        icon=folium.Icon(color="red", icon="star", prefix="fa"),
                    ).add_to(m)
                if len(points) > 1:  # 推荐游玩顺序连线
                    folium.PolyLine(points, color="#ff4d4d", weight=3, opacity=.7,
                                    tooltip="推荐游玩顺序").add_to(m)
                st_folium(m, height=500, use_container_width=True)

    with right:
        if matched is not None:  # 需求筛选模式
            st.markdown(f"**🎯 {city} · 已按需求筛选 {len(info['spots'])} 个景点**")
            for i, (name, sla, slo, cat) in enumerate(info["spots"], 1):
                flag = "✅" if name in matched else "➕"
                st.markdown(f"{i}. {flag} **{name}** · {cat}")
            st.caption("✅ 需求命中 · ➕ 推荐补充 · 点击地图标记查看详情，"
                       "可切换驾车/步行/公交路线")
        else:
            st.markdown(f"**📍 {city} · {len(info['spots'])} 个精选景点**")
            for i, (name, sla, slo, cat) in enumerate(info["spots"], 1):
                st.markdown(f"{i}. **{name}** · {cat}")
            if AMAP_KEY:
                st.caption("高德地图 · 可切换驾车/步行/公交真实路线；点击地图标记查看详情")
            else:
                st.caption("红点连线为建议游玩顺序，点击地图标记查看详情；可在聊天页让 AI 规划详细行程")


# ======================================================================
# 城市交通路线（从某城市出发 → 到达城市）
# ======================================================================
def page_transit():
    _render_nav_bar()
    st.markdown(
        '<div class="chat-header"><div class="ch-logo" style="background:linear-gradient(135deg,'
        '#3498db,#2980b9)">🚄</div><div><div class="ch-title">城市交通路线</div>'
        f'<div class="ch-sub">{len(CITY_GEO)} 城互通 · 跨城驾车路线 · 出行方式建议</div></div></div>',
        unsafe_allow_html=True)

    all_cities = list(CITY_GEO.keys())
    c1, c2 = st.columns(2)
    with c1:
        from_city = st.selectbox("出发城市", all_cities, key="tr_from")
    with c2:
        to_city = st.selectbox("到达城市", [c for c in all_cities if c != from_city],
                               key="tr_to")

    f_lat, f_lng = CITY_GEO[from_city]["center"]
    t_lat, t_lng = CITY_GEO[to_city]["center"]
    dist = _haversine_km(f_lat, f_lng, t_lat, t_lng)

    # 出行方式建议（按直线距离粗估；实际驾车里程以地图路线为准）
    if dist < 150:
        tip = "🚗 距离较近，推荐自驾或城际高铁，当天即可往返"
    elif dist < 800:
        tip = "🚄 推荐高铁出行，快捷舒适；自驾可顺路游玩沿途城市"
    elif dist < 1500:
        tip = "🚄✈️ 高铁与飞机均可，高铁性价比高，飞机更省时"
    else:
        tip = "✈️ 距离较远，推荐乘坐飞机；时间充裕也可选择自驾深度游"
    st.markdown(
        f'<div style="background:#fff9e0;border:2px solid #2b2b2b;border-radius:12px;'
        f'padding:10px 14px;font-weight:700;color:#2b1d0e;box-shadow:3px 3px 0 rgba(43,43,43,.55);">'
        f'📍 {from_city} → {to_city} · 直线约 {dist:.0f} 公里<br/>'
        f'<span style="font-size:.85rem;color:#8a6a3b">{tip}</span></div>',
        unsafe_allow_html=True)

    if AMAP_KEY:
        components.html(_route_map_html(AMAP_KEY, AMAP_SECURITY_JS_CODE,
                                        from_city, to_city),
                        height=540, scrolling=False)
        st.caption("地图显示两城间真实驾车路线与预计里程/时长 · 滚轮缩放 · "
                   "高铁/机票实时信息请以 12306 与航司为准")
    else:
        st.info("未配置高德地图 Key（AMAP_KEY），无法绘制跨城路线；"
                f"{from_city} → {to_city} 直线约 {dist:.0f} 公里")


# ======================================================================
# 我的收藏
# ======================================================================
def page_favorites():
    _render_nav_bar()
    st.markdown(
        '<div class="chat-header"><div class="ch-logo" style="background:linear-gradient(135deg,'
        '#ffd21e,#ff9f1c)">⭐</div><div><div class="ch-title">我的收藏</div>'
        '<div class="ch-sub">收藏的攻略 · 随时回看 · 一键导出</div></div></div>',
        unsafe_allow_html=True)

    data = api_get("/api/favorites")
    items = (data or {}).get("favorites", [])
    if not items:
        st.markdown(
            '<div style="text-align:center;padding:60px 20px;color:#8a6a3b">'
            '<div style="font-size:52px">⭐</div>'
            '<div style="font-size:1.05rem;font-weight:700;margin-top:10px">收藏夹还是空的</div>'
            '<div style="font-size:.85rem;margin-top:6px">在旅行咨询页点击回答下方的 ⭐ 即可收藏攻略</div>'
            '</div>', unsafe_allow_html=True)
        return

    st.caption(f"共 {len(items)} 条收藏")
    for it in items:
        title = it.get("title") or "旅行攻略"
        with st.expander(f"⭐ {title} · {_fmt_time(it.get('created_at', 0))}"):
            st.markdown(it.get("content", ""))
            col1, col2 = st.columns([1, 5])
            with col1:
                st.download_button(
                    "📥 导出", data=it.get("content", "").encode("utf-8"),
                    file_name=f"收藏_{title[:16]}.md", mime="text/markdown",
                    key=f"favdl_{it['id']}", use_container_width=True)
            with col2:
                if st.button("🗑️ 删除", key=f"favdel_{it['id']}",
                             use_container_width=True):
                    try:
                        r = requests.delete(f"{API}/api/favorites/{it['id']}", timeout=10)
                        if r.status_code == 200:
                            st.toast("已删除", icon="🗑️")
                            st.rerun()
                    except Exception as e:
                        st.toast(f"删除失败: {e}", icon="⚠️")


# ======================================================================
# 主入口
# ======================================================================
if "page" not in st.session_state:
    st.session_state.page = "chat"
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "feedbacks" not in st.session_state:
    st.session_state.feedbacks = {}
if "favorited" not in st.session_state:
    st.session_state.favorited = {}
if "voice_text" not in st.session_state:
    st.session_state.voice_text = None
if "tts_idx" not in st.session_state:
    st.session_state.tts_idx = None
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None

load_css()

# 登录门禁：未登录时仅渲染登录 / 注册界面
if not st.session_state.auth_token:
    render_auth()
    st.stop()

# 官网深度链接：?page=chat|map|transit|fav|features|admin|kb 直达对应功能页
_qp_page = st.query_params.get("page")
if _qp_page in ("chat", "map", "transit", "fav", "features", "admin", "kb"):
    st.session_state.page = _qp_page
    st.query_params.clear()

render_sidebar()


# 页面： 产品功能（内嵌品牌官网功能介绍静态页，随应用同源部署）
def page_features():
    _render_nav_bar()
    st.markdown(
        '<div style="margin:6px 0 10px;font-size:.9rem;color:#8a7f6a">'
        '✨ 以下为我们产品的完整功能介绍，也可以在 '
        '<a href="/app/static/features.html" target="_blank">新窗口打开</a> 获得最佳体验'
        '</div>', unsafe_allow_html=True)
    st.components.v1.iframe("/app/static/features.html", height=3800, scrolling=True)


if st.session_state.page == "chat":
    page_chat()
elif st.session_state.page == "features":
    page_features()
elif st.session_state.page == "admin":
    page_admin()
elif st.session_state.page == "fav":
    page_favorites()
elif st.session_state.page == "map":
    page_map()
elif st.session_state.page == "transit":
    page_transit()
else:
    page_kb()
