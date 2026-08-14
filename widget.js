/**
 * Agency AI Voice Receptionist — Floating Click-to-Call Web Widget
 * Embed snippet: <script src="http://127.0.0.1:8100/widget.js" data-agency-id="1"></script>
 */
(function() {
  const currentScript = document.currentScript;
  const agencyId = currentScript ? (currentScript.getAttribute('data-agency-id') || '1') : '1';
  const bridgeHost = currentScript ? new URL(currentScript.src).host : '127.0.0.1:8100';

  // Inject Styles
  const style = document.createElement('style');
  style.textContent = `
    .ai-call-bubble {
      position: fixed; bottom: 24px; right: 24px; z-index: 99999;
      background: linear-gradient(135deg, #1E293B, #0F172A);
      color: #38BDF8; border: 1.5px solid rgba(56, 189, 248, 0.4);
      padding: 12px 20px; border-radius: 30px; cursor: pointer;
      font-family: system-ui, -apple-system, sans-serif; font-size: 14px; font-weight: 600;
      box-shadow: 0 8px 25px rgba(0,0,0,0.3); display: flex; align-items: center; gap: 10px;
      transition: all 0.2s ease;
    }
    .ai-call-bubble:hover { transform: translateY(-2px); box-shadow: 0 12px 30px rgba(56, 189, 248, 0.25); }
    .ai-call-modal {
      position: fixed; bottom: 84px; right: 24px; z-index: 99999;
      width: 340px; background: #0F172A; border: 1px solid #334155; border-radius: 18px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.5); padding: 20px; color: #F8FAFC;
      font-family: system-ui, -apple-system, sans-serif; display: none; flex-direction: column; gap: 14px;
    }
    .ai-call-header { display: flex; justify-content: space-between; align-items: center; }
    .ai-call-title { font-size: 15px; font-weight: 700; color: #F8FAFC; }
    .ai-call-status { font-size: 12px; color: #94A3B8; display: flex; align-items: center; gap: 6px; }
    .ai-call-dot { width: 8px; height: 8px; border-radius: 50%; background: #34D399; }
    .ai-call-transcript {
      height: 180px; overflow-y: auto; background: #1E293B; border-radius: 12px;
      padding: 12px; font-size: 13px; display: flex; flex-direction: column; gap: 8px;
    }
    .ai-msg { padding: 6px 10px; border-radius: 8px; max-width: 90%; line-height: 1.4; }
    .ai-msg-bot { background: #334155; color: #F8FAFC; align-self: flex-start; }
    .ai-msg-user { background: rgba(56, 189, 248, 0.2); color: #38BDF8; align-self: flex-end; }
    .ai-call-actions { display: flex; gap: 8px; }
    .ai-btn-hangup {
      flex: 1; padding: 10px; background: #EF4444; color: white; border: none;
      border-radius: 10px; font-weight: 600; font-size: 13px; cursor: pointer;
    }
  `;
  document.head.appendChild(style);

  // Inject DOM Elements
  const bubble = document.createElement('div');
  bubble.className = 'ai-call-bubble';
  bubble.innerHTML = `<span>📞</span> <span>Talk to AI Receptionist</span>`;

  const modal = document.createElement('div');
  modal.className = 'ai-call-modal';
  modal.innerHTML = `
    <div class="ai-call-header">
      <div>
        <div class="ai-call-title">AI Receptionist</div>
        <div class="ai-call-status"><span class="ai-call-dot"></span> Live Voice Call</div>
      </div>
      <button style="background:none;border:none;color:#94A3B8;cursor:pointer;font-size:18px;" id="aiCloseBtn">✕</button>
    </div>
    <div class="ai-call-transcript" id="aiTranscript"></div>
    <div class="ai-call-actions">
      <button class="ai-btn-hangup" id="aiHangupBtn">End Call</button>
    </div>
  `;

  document.body.appendChild(bubble);
  document.body.appendChild(modal);

  let ws = null;
  let recognition = null;
  let isCallActive = false;

  function speakText(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05;
    u.lang = 'en-US';
    window.speechSynthesis.speak(u);
  }

  function appendMsg(role, text) {
    const box = document.getElementById('aiTranscript');
    if (!box) return;
    const m = document.createElement('div');
    m.className = `ai-msg ai-msg-${role}`;
    m.textContent = text;
    box.appendChild(m);
    box.scrollTop = box.scrollHeight;
  }

  function startCall() {
    modal.style.display = 'flex';
    bubble.style.display = 'none';
    isCallActive = true;

    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${wsProto}//${bridgeHost}/ws/call/${agencyId}`);

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'bot_speech') {
        appendMsg('bot', data.text);
        speakText(data.text);
      } else if (data.type === 'call_ended') {
        appendMsg('bot', 'Call ended. Lead details recorded.');
      }
    };

    // Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = 'en-US';
      recognition.onresult = (e) => {
        const last = e.results[e.results.length - 1];
        if (last.isFinal) {
          const userText = last[0].transcript.trim();
          if (userText && ws && ws.readyState === WebSocket.OPEN) {
            appendMsg('user', userText);
            ws.send(JSON.stringify({ type: 'user_speech', text: userText }));
          }
        }
      };
      recognition.onend = () => {
        if (isCallActive) {
          try { recognition.start(); } catch(err) {}
        }
      };
      try { recognition.start(); } catch(err) {}
    }
  }

  function endCall() {
    isCallActive = false;
    if (recognition) { try { recognition.stop(); } catch(e) {} }
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'end_call' }));
      setTimeout(() => ws.close(), 300);
    }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    modal.style.display = 'none';
    bubble.style.display = 'flex';
  }

  bubble.addEventListener('click', startCall);
  document.getElementById('aiHangupBtn').addEventListener('click', endCall);
  document.getElementById('aiCloseBtn').addEventListener('click', endCall);
})();
