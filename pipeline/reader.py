#!/usr/bin/env python3
"""Read-aloud controls for long-form pages.

Uses the browser's own speech engine, which costs nothing and needs no key. The
quality is set by the voices the reader has installed: macOS Enhanced and
Premium voices are close to natural, the default ones are not, so the picker
sorts good voices to the top and says where to get them.

Two decisions matter more than the voice:

  Numbers are rewritten before speaking. "$164.7bn" spoken literally becomes
  "dollar one six four point seven b n". It has to become "164.7 billion
  dollars" or the whole thing is unlistenable.

  Financial tables are skipped. Reading a balance sheet cell by cell is
  useless to a listener, and the prose around each statement already carries
  the figures that matter in speakable form.
"""

READER_CSS = """
.rdr{position:sticky;top:0;z-index:40;display:flex;align-items:center;gap:10px;
  padding:9px 0;margin-bottom:18px;background:var(--paper);
  border-bottom:1px solid var(--rule)}
.rdr button{font-family:var(--sans);font-size:13px;font-weight:500;
  background:var(--raise);color:var(--ink);border:1px solid var(--rule);
  border-radius:5px;padding:7px 13px;cursor:pointer;line-height:1}
.rdr button:hover{border-color:var(--ember)}
.rdr button.go{background:var(--ember);color:#fff;border-color:var(--ember)}
.rdr select{font-family:var(--mono);font-size:11.5px;background:var(--raise);
  color:var(--ink2);border:1px solid var(--rule);border-radius:5px;
  padding:6px 8px;max-width:190px}
.rdr .st{font-family:var(--mono);font-size:11px;color:var(--ink3);
  letter-spacing:.06em;margin-left:auto;white-space:nowrap}
.rdr-hint{font-size:12.5px;color:var(--ink3);margin:-8px 0 20px}
.rdr-hint a{color:var(--ember)}
.speaking{background:var(--raise);box-shadow:-14px 0 0 var(--raise),
  14px 0 0 var(--raise);border-radius:2px}
@media print{.rdr,.rdr-hint{display:none}}
"""

READER_HTML = """
<div class="rdr">
  <button id="rdrPlay" class="go">&#9654;&nbsp; Read aloud</button>
  <button id="rdrStop">Stop</button>
  <select id="rdrVoice" aria-label="Voice"></select>
  <select id="rdrRate" aria-label="Speed">
    <option value="0.9">0.9&times;</option>
    <option value="1" selected>1.0&times;</option>
    <option value="1.15">1.15&times;</option>
    <option value="1.3">1.3&times;</option>
  </select>
  <span class="st" id="rdrStat"></span>
</div>
<p class="rdr-hint" id="rdrHint"></p>
"""

READER_JS = """<script>
(function(){
  var synth = window.speechSynthesis;
  var bar = document.querySelector(".rdr");
  if(!synth || !bar){ if(bar) bar.style.display="none"; return; }

  var playBtn=document.getElementById("rdrPlay"), stopBtn=document.getElementById("rdrStop"),
      voiceSel=document.getElementById("rdrVoice"), rateSel=document.getElementById("rdrRate"),
      stat=document.getElementById("rdrStat"), hint=document.getElementById("rdrHint");

  // ---- what gets read -------------------------------------------------
  // Prose and headings only. Statement tables are deliberately excluded:
  // read aloud, a balance sheet is a stream of digits nobody can follow.
  var nodes = Array.prototype.slice.call(
    document.querySelectorAll(".wrap h1, .wrap h2, .wrap p.lede, .wrap .qb p, " +
                              ".wrap > p, .wrap .why, .wrap .lesson h4, .wrap .warn p"))
    .filter(function(n){
      // .rdr-hint is a sibling of the control bar, not inside it, so it would
      // otherwise be read out: the reader reciting its own setup instructions.
      if(n.classList.contains("rdr-hint")) return false;
      if(n.closest(".rdr")||n.closest(".stmt")||n.closest(".tie")) return false;
      return n.textContent.trim().length > 25;
    });
  if(!nodes.length){ bar.style.display="none"; return; }

  // ---- make the text speakable ---------------------------------------
  function speakable(t){
    return t
      .replace(/\\u00a0/g," ")
      .replace(/\\$([\\d,.]+)\\s*bn/gi, "$1 billion dollars")
      .replace(/\\$([\\d,.]+)\\s*m\\b/gi, "$1 million dollars")
      .replace(/\\$([\\d,.]+)/g, "$1 dollars")
      .replace(/([\\d.]+)\\s*pp\\b/gi, "$1 percentage points")
      .replace(/([\\d.]+)%/g, "$1 percent")
      .replace(/\\b10-K\\b/g, "ten K").replace(/\\b10-Q\\b/g, "ten Q")
      .replace(/\\b8-K\\b/g, "eight K")
      .replace(/\\bMD&A\\b/g, "M D and A")
      .replace(/\\bTTM\\b/g, "trailing twelve month")
      .replace(/\\bEV\\b/g, "enterprise value")
      .replace(/\\bROE\\b/g, "return on equity").replace(/\\bROIC\\b/g,"return on invested capital")
      .replace(/\\bFCF\\b/g, "free cash flow")
      .replace(/\\bP\\s*\\/\\s*E\\b/g, "price to earnings")
      .replace(/&/g, " and ")
      .replace(/\\u2014|\\u2013/g, ", ")
      .replace(/\\s+/g, " ").trim();
  }

  // Long utterances get truncated by some engines, so split on sentences.
  var queue=[];
  nodes.forEach(function(n,i){
    var parts = speakable(n.textContent).match(/[^.!?]+[.!?]*/g) || [];
    parts.forEach(function(p){
      p=p.trim(); if(p.length>1) queue.push({node:n, text:p, idx:i});
    });
  });

  // ---- voices ---------------------------------------------------------
  var voices=[], chosen=null;
  function rank(v){
    var n=(v.name||"").toLowerCase(), s=0;
    if(/premium|enhanced|natural|siri/.test(n)) s+=100;   // the good ones
    if(/^en-gb/i.test(v.lang)) s+=20;
    if(/^en/i.test(v.lang)) s+=10;
    if(v.localService) s+=2;
    return s;
  }
  function loadVoices(){
    voices = synth.getVoices().filter(function(v){ return /^en/i.test(v.lang); });
    if(!voices.length) return;
    voices.sort(function(a,b){ return rank(b)-rank(a); });
    voiceSel.innerHTML = voices.map(function(v,i){
      var good = /premium|enhanced|natural|siri/i.test(v.name);
      return '<option value="'+i+'">'+(good?"\\u2605 ":"")+v.name+"</option>";
    }).join("");
    chosen = voices[0];
    var anyGood = voices.some(function(v){ return /premium|enhanced|natural|siri/i.test(v.name); });
    hint.innerHTML = anyGood ? "" :
      "Only basic voices are installed. For a far better one: System Settings " +
      "\\u2192 Accessibility \\u2192 Spoken Content \\u2192 System Voice \\u2192 " +
      "Manage Voices, then download an <b>Enhanced</b> or <b>Premium</b> English voice.";
  }
  loadVoices();
  if(synth.onvoiceschanged !== undefined) synth.onvoiceschanged = loadVoices;
  voiceSel.addEventListener("change", function(){ chosen = voices[this.value]; restartIfSpeaking(); });
  rateSel.addEventListener("change", restartIfSpeaking);

  // ---- playback -------------------------------------------------------
  var at=0, playing=false, last=null;
  function mark(n){
    if(last) last.classList.remove("speaking");
    if(n){ n.classList.add("speaking");
           n.scrollIntoView({block:"center", behavior:"smooth"}); }
    last=n;
  }
  function status(){
    stat.textContent = playing ? (queue[at] ? "part " + (queue[at].idx+1) + " of " + nodes.length : "")
                               : (at>0 && at<queue.length ? "paused" : "");
  }
  function speakNext(){
    if(!playing || at>=queue.length){ finish(); return; }
    var item=queue[at];
    mark(item.node);
    var u=new SpeechSynthesisUtterance(item.text);
    if(chosen) u.voice=chosen;
    u.rate=parseFloat(rateSel.value)||1; u.pitch=1;
    u.onend=function(){ at++; status(); speakNext(); };
    u.onerror=function(){ at++; speakNext(); };
    synth.speak(u);
    status();
  }
  function finish(){
    playing=false; synth.cancel(); mark(null); at=0;
    playBtn.innerHTML="&#9654;&nbsp; Read aloud"; playBtn.classList.add("go"); status();
  }
  function restartIfSpeaking(){
    if(!playing) return;
    synth.cancel();
    setTimeout(speakNext, 60);            // let cancel settle before re-queuing
  }
  playBtn.addEventListener("click", function(){
    if(playing){
      playing=false; synth.cancel();
      playBtn.innerHTML="&#9654;&nbsp; Resume"; playBtn.classList.add("go"); status();
    } else {
      playing=true;
      playBtn.innerHTML="&#10073;&#10073;&nbsp; Pause"; playBtn.classList.remove("go");
      speakNext();
    }
  });
  stopBtn.addEventListener("click", finish);
  window.addEventListener("beforeunload", function(){ synth.cancel(); });
})();
</script>"""
