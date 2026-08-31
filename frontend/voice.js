(function () {
  const input = document.getElementById("replyInput");
  const voiceBtn = document.getElementById("voiceBtn");
  const speakBtn = document.getElementById("speakBtn");
  const status = document.getElementById("voiceStatus");
  const mentorLine = document.getElementById("mentorLine");

  if (!input || !voiceBtn || !speakBtn || !status) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let listening = false;

  function setStatus(text) {
    status.textContent = text;
  }

  function setMentor(text) {
    if (mentorLine) mentorLine.textContent = text;
  }

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = "zh-CN";
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = function () {
      listening = true;
      voiceBtn.classList.add("listening");
      setStatus("正在听你回应");
      setMentor("说慢点，我负责抓重点，不负责替你吵架。");
    };

    recognition.onresult = function (event) {
      let finalText = "";
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += transcript;
        else interimText += transcript;
      }
      const next = (input.value + " " + finalText + interimText).trim();
      input.value = next;
    };

    recognition.onerror = function () {
      setStatus("语音输入失败，可继续打字");
      setMentor("麦克风不给面子，手打也能赢。重点是别上头。");
    };

    recognition.onend = function () {
      listening = false;
      voiceBtn.classList.remove("listening");
      setStatus("语音待命");
    };
  } else {
    voiceBtn.disabled = true;
    setStatus("当前浏览器不支持语音输入");
  }

  voiceBtn.addEventListener("click", function () {
    if (!recognition) return;
    if (listening) {
      recognition.stop();
      return;
    }
    input.value = "";
    recognition.start();
  });

  speakBtn.addEventListener("click", function () {
    if (!window.speechSynthesis) {
      setStatus("当前浏览器不支持朗读");
      return;
    }
    const bubbles = Array.from(document.querySelectorAll(".turn.opponent .bubble"));
    const latest = bubbles.at(-1);
    const text = latest ? latest.textContent.trim() : "请选择一个场景开始训练。";
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = /[a-zA-Z]/.test(text) ? "en-US" : "zh-CN";
    utterance.rate = 0.92;
    utterance.pitch = 0.72;
    utterance.onstart = function () {
      setStatus("正在朗读 NPC");
      setMentor("听清楚对方怎么施压，然后用规则拆掉它。 ");
    };
    utterance.onend = function () {
      setStatus("语音待命");
    };
    window.speechSynthesis.speak(utterance);
  });

  document.addEventListener("submit", function () {
    const lines = [
      "不错，牙尖可以，但方向得是自保。",
      "边界说出来，冲突就少一半戏份。",
      "记住：赢不是吵赢，是安全离场。",
      "如果对方上头，你就更不能把方向盘交出去。",
    ];
    setMentor(lines[Math.floor(Math.random() * lines.length)]);
  });
})();
