/* ============================================================
 * MC互通管家 远程控制面板 - 原生 JS
 * 零依赖，离线可用
 * ============================================================ */
(function () {
  'use strict';

  // ---------- 常量 ----------
  const LS_KEY = 'mcbridge.session.v1';
  const DEFAULT_PORT = 8765;
  const LOG_POLL_MS = 2000;
  const STATUS_POLL_MS = 3000;
  const FETCH_TIMEOUT_MS = 8000;

  // ---------- DOM ----------
  const $ = (sel) => document.querySelector(sel);
  const screens = {
    pair: $('#screen-pair'),
    console: $('#screen-console'),
  };
  const els = {
    codeInput: $('#code-input'),
    pairError: $('#pair-error'),
    btnConnect: $('#btn-connect'),
    hostInput: $('#host-input'),

    hostLine: $('#host-line'),
    btnDisconnect: $('#btn-disconnect'),

    dotRunning: $('#dot-running'),
    textRunning: $('#text-running'),
    textPlayers: $('#text-players'),
    textJavaPort: $('#text-java-port'),
    textBedrockPort: $('#text-bedrock-port'),
    textMem: $('#text-mem'),
    playersChips: $('#players-chips'),

    btnStart: $('#btn-start'),
    btnStop: $('#btn-stop'),
    btnRestart: $('#btn-restart'),

    logBox: $('#log-box'),
    btnClearLog: $('#btn-clear-log'),

    configForm: $('#config-form'),
    configHint: $('#config-hint'),

    modal: $('#modal'),
    modalTitle: $('#modal-title'),
    modalBody: $('#modal-body'),
    modalOk: $('#modal-ok'),
    modalCancel: $('#modal-cancel'),

    toast: $('#toast'),
  };

  // ---------- 状态 ----------
  let session = loadSession(); // {host, token}
  let logNext = 0;
  let logTimer = null;
  let statusTimer = null;
  let pendingModalAction = null;

  // ============================================================
  // 工具
  // ============================================================
  function loadSession() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (obj && obj.host && obj.token) return obj;
    } catch (e) { /* ignore */ }
    return null;
  }
  function saveSession(s) {
    session = s;
    if (s) localStorage.setItem(LS_KEY, JSON.stringify(s));
    else localStorage.removeItem(LS_KEY);
  }

  function normalizeHost(input) {
    if (!input) return '';
    let h = String(input).trim().replace(/^https?:\/\//i, '').replace(/\/+$/, '');
    // 若没带端口，补默认端口
    if (!/:\d+$/.test(h)) h = h + ':' + DEFAULT_PORT;
    return 'http://' + h;
  }

  async function api(path, { method = 'GET', body, auth = true, timeout = FETCH_TIMEOUT_MS } = {}) {
    const url = (session ? session.host : '') + path;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    const headers = { 'Content-Type': 'application/json' };
    if (auth && session && session.token) headers['Authorization'] = 'Bearer ' + session.token;
    let resp;
    try {
      resp = await fetch(url, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
    } catch (e) {
      clearTimeout(timer);
      if (e.name === 'AbortError') throw new Error('请求超时，请检查局域网连接');
      throw new Error('无法连接到服务器，请确认电脑与手机在同一 Wi-Fi 且桌面端已启动');
    }
    clearTimeout(timer);

    let data = null;
    const text = await resp.text();
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = { raw: text }; }
    }
    if (resp.status === 401) {
      // token 失效
      handleUnauthorized();
      const err = new Error('连接已失效，请重新配对');
      err.code = 401;
      throw err;
    }
    if (!resp.ok) {
      const msg = (data && (data.error || data.message)) || ('HTTP ' + resp.status);
      const err = new Error(msg);
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  function handleUnauthorized() {
    saveSession(null);
    stopLoops();
    showScreen('pair');
    showPairError('登录态已失效（401），请重新输入连接码');
  }

  function toast(msg, ms = 2200) {
    els.toast.textContent = msg;
    els.toast.classList.remove('hidden');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => els.toast.classList.add('hidden'), ms);
  }

  function showPairError(msg) {
    els.pairError.textContent = msg;
    els.pairError.classList.remove('hidden');
  }
  function clearPairError() {
    els.pairError.classList.add('hidden');
    els.pairError.textContent = '';
  }

  function showScreen(name) {
    screens.pair.classList.toggle('hidden', name !== 'pair');
    screens.console.classList.toggle('hidden', name !== 'console');
    window.scrollTo(0, 0);
  }

  // ============================================================
  // 首屏：配对
  // ============================================================
  function initPair() {
    const params = new URLSearchParams(location.search);
    const code = (params.get('code') || '').replace(/\D/g, '').slice(0, 6);
    const host = params.get('host') || '';

    if (host) els.hostInput.value = host.replace(/^https?:\/\//i, '').replace(/:\d+$/, '');

    // 自动配对
    if (code && host) {
      els.codeInput.value = code;
      doPair(code, host);
    } else if (code) {
      els.codeInput.value = code;
      // 没有 host，尝试自动配对（从 localStorage 或让用户输入）
      if (session && session.host) {
        doPair(code, session.host);
      }
    }

    els.codeInput.addEventListener('input', () => {
      // 仅保留数字
      const v = els.codeInput.value.replace(/\D/g, '').slice(0, 6);
      els.codeInput.value = v;
      clearPairError();
      if (v.length === 6 && els.hostInput.value.trim()) {
        // 自动提交
        doPair(v, els.hostInput.value.trim());
      }
    });

    els.btnConnect.addEventListener('click', () => {
      const code = els.codeInput.value.trim();
      const host = els.hostInput.value.trim();
      if (!code || code.length !== 6) {
        showPairError('请输入 6 位数字连接码');
        return;
      }
      if (!host) {
        showPairError('请在「高级」中填写主机 IP（如 192.168.1.100）');
        return;
      }
      doPair(code, host);
    });

    // 回车提交
    els.codeInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') els.btnConnect.click();
    });
  }

  async function doPair(code, hostRaw) {
    clearPairError();
    setConnectLoading(true);
    try {
      const host = normalizeHost(hostRaw);
      // 配对时无 token，手动 fetch
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      let resp;
      try {
        resp = await fetch(host + '/api/v1/pair', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: String(code) }),
          signal: ctrl.signal,
        });
      } catch (e) {
        clearTimeout(timer);
        if (e.name === 'AbortError') throw new Error('连接超时，请确认桌面端已启动且手机在同一局域网');
        throw new Error('无法连接到 ' + host + '，请检查 IP 与端口');
      }
      clearTimeout(timer);

      let data = null;
      const text = await resp.text();
      if (text) { try { data = JSON.parse(text); } catch (_) {} }

      if (resp.status === 401 || resp.status === 400) {
        throw new Error('连接码错误或已过期，请在桌面端刷新后重试');
      }
      if (!resp.ok || !data || !data.token) {
        throw new Error('配对失败：' + ((data && (data.error || data.message)) || ('HTTP ' + resp.status)));
      }

      saveSession({ host, token: data.token });
      // 清理 URL 参数，避免刷新重复配对
      history.replaceState(null, '', location.pathname);
      enterConsole();
    } catch (e) {
      showPairError(e.message || '连接失败');
    } finally {
      setConnectLoading(false);
    }
  }

  function setConnectLoading(loading) {
    els.btnConnect.disabled = loading;
    els.btnConnect.querySelector('.btn-label').textContent = loading ? '连接中…' : '连 接';
    els.btnConnect.querySelector('.btn-spinner').classList.toggle('hidden', !loading);
  }

  // ============================================================
  // 控制台
  // ============================================================
  function enterConsole() {
    showScreen('console');
    els.hostLine.textContent = session.host.replace(/^https?:\/\//, '');
    loadConfig();
    startLoops();
    // 立即拉一次状态与日志
    refreshStatus();
    refreshLogs(true);
  }

  function startLoops() {
    stopLoops();
    statusTimer = setInterval(refreshStatus, STATUS_POLL_MS);
    logTimer = setInterval(() => refreshLogs(false), LOG_POLL_MS);
  }
  function stopLoops() {
    if (statusTimer) { clearInterval(statusTimer); statusTimer = null; }
    if (logTimer) { clearInterval(logTimer); logTimer = null; }
  }

  async function refreshStatus() {
    try {
      const s = await api('/api/v1/status');
      renderStatus(s);
    } catch (e) {
      // 401 已全局处理；其他错误静默或红点
      if (e.code !== 401) {
        els.dotRunning.className = 'dot offline';
        els.textRunning.textContent = '离线';
      }
    }
  }

  function renderStatus(s) {
    const running = !!s.running;
    els.dotRunning.className = 'dot ' + (running ? 'online' : 'offline');
    els.textRunning.textContent = running ? '运行中' : '已停止';

    els.textPlayers.textContent = `${s.players_online ?? 0} / ${s.players_max ?? '–'}`;

    els.textJavaPort.textContent = s.java_port_listening ? '监听中' : '未监听';
    els.textBedrockPort.textContent = s.bedrock_port_listening ? '监听中' : '未监听';

    els.textMem.textContent = `${Math.round(s.mem_used_mb ?? 0)} / ${Math.round(s.mem_total_mb ?? 0)} MB`;

    // 玩家 chips
    const list = Array.isArray(s.players_list) ? s.players_list : [];
    if (list.length === 0) {
      els.playersChips.className = 'chips empty';
      els.playersChips.textContent = '暂无玩家';
    } else {
      els.playersChips.className = 'chips';
      els.playersChips.innerHTML = '';
      list.forEach((p) => {
        const name = typeof p === 'string' ? p : (p.name || p.username || JSON.stringify(p));
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = name;
        els.playersChips.appendChild(chip);
      });
    }
  }

  async function refreshLogs(reset) {
    try {
      const since = reset ? 0 : logNext;
      const data = await api('/api/v1/logs?n=200&since=' + since);
      if (reset) {
        els.logBox.textContent = '';
      }
      if (data && Array.isArray(data.lines) && data.lines.length) {
        const shouldScroll = isScrolledToBottom();
        data.lines.forEach((line) => appendLogLine(line));
        if (shouldScroll || reset) scrollLogBottom();
      }
      if (data && typeof data.next === 'number') logNext = data.next;
    } catch (e) { /* 静默 */ }
  }

  function appendLogLine(line) {
    if (line === undefined || line === null) return;
    if (els.logBox.textContent.length > 200000) {
      // 防止内存爆掉，截断前一半
      const half = els.logBox.textContent.length / 2;
      els.logBox.textContent = els.logBox.textContent.slice(half);
    }
    els.logBox.textContent += (typeof line === 'string' ? line : JSON.stringify(line)) + '\n';
  }
  function isScrolledToBottom() {
    const el = els.logBox;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 30;
  }
  function scrollLogBottom() {
    els.logBox.scrollTop = els.logBox.scrollHeight;
  }

  els.btnClearLog.addEventListener('click', () => {
    els.logBox.textContent = '';
  });

  // ---------- 启动/停止/重启 ----------
  function bindAction(btn, path, confirmTitle, confirmBody) {
    btn.addEventListener('click', () => {
      showModal(confirmTitle, confirmBody, async () => {
        try {
          await api(path, { method: 'POST' });
          toast('操作已下发');
          setTimeout(refreshStatus, 800);
          setTimeout(() => refreshLogs(true), 1500);
        } catch (e) {
          if (e.code !== 401) toast('操作失败：' + e.message);
        }
      });
    });
  }
  bindAction(els.btnStart, '/api/v1/start', '启动服务器', '确定要启动 Minecraft 服务器吗？');
  bindAction(els.btnStop, '/api/v1/stop', '停止服务器', '停止后所有在线玩家将被断开，确定继续？');
  bindAction(els.btnRestart, '/api/v1/restart', '重启服务器', '服务器将重启，过程中会短暂不可用，确定继续？');

  // ---------- 配置 ----------
  async function loadConfig() {
    try {
      const c = await api('/api/v1/config');
      fillConfigForm(c);
    } catch (e) {
      /* 401 已处理 */
    }
  }
  function fillConfigForm(c) {
    if (!c) return;
    const f = els.configForm;
    if (c.motd != null) f.motd.value = c.motd;
    if (c.difficulty) f.difficulty.value = c.difficulty;
    if (c.gamemode) f.gamemode.value = c.gamemode;
    if (c.max_players != null) f.max_players.value = c.max_players;
    if (c.xms != null) f.xms.value = c.xms;
    if (c.xmx != null) f.xmx.value = c.xmx;
    f.online_mode.checked = !!c.online_mode;
    f.floodgate_enabled.checked = !!c.floodgate_enabled;
  }

  els.configForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = els.configForm;
    const body = {
      motd: f.motd.value.trim(),
      difficulty: f.difficulty.value,
      gamemode: f.gamemode.value,
      max_players: parseInt(f.max_players.value, 10) || 100,
      xms: f.xms.value.trim(),
      xmx: f.xmx.value.trim(),
      online_mode: !!f.online_mode.checked,
      floodgate_enabled: !!f.floodgate_enabled.checked,
    };
    // 去掉空字符串内存项
    if (!body.xms) delete body.xms;
    if (!body.xmx) delete body.xmx;
    try {
      await api('/api/v1/config', { method: 'PUT', body });
      toast('配置已保存，重启后生效');
    } catch (err) {
      if (err.code !== 401) toast('保存失败：' + err.message);
    }
  });

  // ---------- 断开 ----------
  els.btnDisconnect.addEventListener('click', () => {
    showModal('断开连接', '将清除本机保存的配对信息，确定断开？', () => {
      saveSession(null);
      stopLoops();
      els.logBox.textContent = '';
      logNext = 0;
      showScreen('pair');
      els.codeInput.value = '';
      toast('已断开');
    });
  });

  // ============================================================
  // 弹窗
  // ============================================================
  function showModal(title, body, onOk) {
    els.modalTitle.textContent = title;
    els.modalBody.textContent = body;
    pendingModalAction = onOk;
    els.modal.classList.remove('hidden');
  }
  function hideModal() {
    els.modal.classList.add('hidden');
    pendingModalAction = null;
  }
  els.modalCancel.addEventListener('click', hideModal);
  els.modal.querySelector('.modal-mask').addEventListener('click', hideModal);
  els.modalOk.addEventListener('click', () => {
    const fn = pendingModalAction;
    hideModal();
    if (typeof fn === 'function') fn();
  });

  // ============================================================
  // 启动
  // ============================================================
  function boot() {
    initPair();
    if (session && session.host && session.token) {
      enterConsole();
    } else {
      showScreen('pair');
    }
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
