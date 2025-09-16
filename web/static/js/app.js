let currentTool = 'crop';
let primaryFile = null;
let fileQueue = [];
let wavesurfer = null;
let wsOut = null;

// Tool Configurations
const TOOLS = {
  crop: { icon: "✂️", title: "Crop / Trim", desc: "Cut audio between two specific timestamps." },
  merge: { icon: "🔗", title: "Merge Tracks", desc: "Join multiple audio files end-to-end.", multi: true },
  overlay: { icon: "🔀", title: "Overlay", desc: "Mix multiple audio tracks together.", multi: true },
  volume: { icon: "🔊", title: "Volume Control", desc: "Increase or decrease volume (dB)." },
  convert: { icon: "🔄", title: "Convert Format", desc: "Convert between formats like MP3, WAV, FLAC." },
  speed: { icon: "⏩", title: "Change Speed", desc: "Speed up or slow down the audio playback." },
  fade: { icon: "🌅", title: "Fade Effects", desc: "Add smooth fade in or fade out effects." },
  reverse: { icon: "🔁", title: "Reverse Audio", desc: "Reverse the playback of the audio file." },
  normalize: { icon: "🔉", title: "Normalize", desc: "Auto-balance volume to a target level." },
  silence: { icon: "🔇", title: "Strip Silence", desc: "Automatically remove silent gaps from the track." },
  extract: { icon: "🎬", title: "Extract from Video", desc: "Rip the audio track from any video file.", video: true },
  transcribe: { icon: "📝", title: "Speech to Text", desc: "Extract spoken words into text using AI.", video: true, text: true },
  besttakes: { icon: "✂️", title: "Auto Best Takes", desc: "AI instantly snips dead air and crossfades the spoken words into a fast-paced cut." },
  isolate: { icon: "👤", title: "Vocal Isolation", desc: "Separate vocals from instrumental." },
  master: { icon: "🪄", title: "AI Mastering", desc: "Auto EQ and limiting for loudness." },
  tts: { icon: "🎤", title: "AI Voiceovers", desc: "Generate realistic speech from text.", hideDropzone: true },
  visualizer: { icon: "🎥", title: "Audio Visualizer", desc: "Generate MP4 with reactive waveform." },
  fx: { icon: "🎛", title: "Pro FX", desc: "Apply real-time Reverb and EQ." },
  "8d": { icon: "🎧", title: "8D Audio", desc: "Immersive 3D Spatial Audio panning." },
  batch: { icon: "⚙️", title: "Batch Engine", desc: "Process 100+ files instantly in the background.", multi: true }
};

function initTheme() {
  const saved = localStorage.getItem('aryan_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  const sel = document.getElementById('theme-switch');
  if (sel) sel.value = saved;
  setTimeout(() => {
    const c = getComputedStyle(document.documentElement).getPropertyValue('--bg-surface').trim();
    if (c) document.getElementById('theme-color-meta')?.setAttribute('content', c);
  }, 50);
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNav();
  initDropzone();
  switchTool('crop');
});

function initNav() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      switchTool(e.currentTarget.dataset.tool);
    });
  });
}

function switchTool(toolId) {
  if (document.startViewTransition) {
    document.startViewTransition(() => updateToolDOM(toolId));
  } else {
    updateToolDOM(toolId);
  }
}

function updateToolDOM(toolId) {
  currentTool = toolId;
  const config = TOOLS[toolId];
  
  // Update Canvas Header
  document.getElementById('canvas-title').innerText = `${config.icon} ${config.title}`;
  document.getElementById('canvas-desc').innerText = config.desc;
  
  // Update Dropzone Acceptance
  const dzInput = document.getElementById('dz-input');
  if (config.video) {
    dzInput.accept = ".mp3,.wav,.ogg,.flac,.aac,.m4a,.wma,.opus,.mp4,.mkv,.avi,.mov,.webm,.flv,.wmv,.m4v,.3gp";
  } else {
    dzInput.accept = ".mp3,.wav,.ogg,.flac,.aac,.m4a,.wma,.opus";
  }

  // Toggle Inspector Panels
  document.querySelectorAll('.inspector-section').forEach(s => s.classList.remove('active'));
  const insp = document.getElementById(`insp-${toolId}`);
  if (insp) insp.classList.add('active');
  
  // Just re-render UI instead of wiping data
  updateFileUI();
}

function resetWorkspace() {
  primaryFile = null;
  fileQueue = [];
  updateFileUI();
  document.getElementById('run-btn').disabled = true;
  document.getElementById('transcribe-output').style.display = 'none';
  document.getElementById('result-container').style.display = 'none';
  if (wsOut) { wsOut.destroy(); wsOut = null; }
}

// ── Dropzone & File Handling ──
function initDropzone() {
  const dz = document.getElementById('dropzone');
  const input = document.getElementById('dz-input');
  const canvas = document.getElementById('canvas');
  
  dz.addEventListener('click', () => input.click());
  
  // Make the entire main canvas accept drops
  canvas.addEventListener('dragover', e => { 
    e.preventDefault(); 
    dz.classList.add('dragover'); 
  });
  canvas.addEventListener('dragleave', e => { 
    e.preventDefault();
    dz.classList.remove('dragover'); 
  });
  canvas.addEventListener('drop', e => {
    e.preventDefault();
    dz.classList.remove('dragover');
    if (e.dataTransfer && e.dataTransfer.files) {
      handleFiles(e.dataTransfer.files);
    }
  });
  
  input.addEventListener('change', e => handleFiles(e.target.files));
  
  // Microphone Recording Logic
  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;
  const recordBtn = document.getElementById('record-btn');
  
  recordBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.ondataavailable = e => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };
        
        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
          const file = new File([audioBlob], `Studio_Recording.webm`, { type: 'audio/webm' });
          handleFiles([file]);
          stream.getTracks().forEach(t => t.stop());
        };
        
        mediaRecorder.start();
        isRecording = true;
        recordBtn.innerHTML = '<i class="ph-fill ph-stop"></i> Stop Recording';
        recordBtn.classList.add('recording-pulse');
      } catch(err) {
        showToast('Microphone access denied', 'error');
      }
    } else {
      mediaRecorder.stop();
      isRecording = false;
      recordBtn.innerHTML = '<i class="ph-fill ph-microphone"></i> Start Recording';
      recordBtn.classList.remove('recording-pulse');
    }
  });
}

function handleFiles(files) {
  const validFiles = Array.from(files).filter(f => f.type.startsWith('audio/') || f.type.startsWith('video/'));
  if (validFiles.length === 0) {
    showToast('Invalid file type. Please upload audio or video files.', 'error');
    return;
  }
  
  // Hide previous result when new files are dropped
  document.getElementById('result-container').style.display = 'none';
  if (wsOut) { wsOut.destroy(); wsOut = null; }
  
  if (TOOLS[currentTool].multi) {
    fileQueue = [...fileQueue, ...validFiles];
  } else {
    primaryFile = validFiles[0];
  }
  updateFileUI();
}

function updateFileUI() {
  const config = TOOLS[currentTool];
  const dz = document.getElementById('dropzone');
  const wfContainer = document.getElementById('waveform-container');
  const qContainer = document.getElementById('queue-container');
  const runBtn = document.getElementById('run-btn');
  
  // Sync single and multi state so switching tools doesn't lose files
  if (config.multi && fileQueue.length === 0 && primaryFile) {
    fileQueue = [primaryFile];
  } else if (!config.multi && !primaryFile && fileQueue.length > 0) {
    primaryFile = fileQueue[0];
  }

  if (config.hideDropzone) {
    dz.classList.add('hidden');
    wfContainer.style.display = 'none';
    qContainer.style.display = 'none';
    runBtn.disabled = false;
    return;
  }
  
  if (config.multi) {
    dz.classList.remove('hidden');
    wfContainer.style.display = 'none';
    
    if (fileQueue.length === 0) {
      qContainer.style.display = 'none';
      runBtn.disabled = true;
      if (window.queueWavesurfers) {
        window.queueWavesurfers.forEach(ws => ws && ws.destroy());
        window.queueWavesurfers = [];
        window.queueRegions = [];
      }
    } else {
      qContainer.style.display = 'block';
      if(currentTool==='merge'||currentTool==='overlay'){ renderTimeline(); } else { renderQueue(); }
      document.getElementById('meta-size').innerText = `${(fileQueue.reduce((a,b)=>a+b.size, 0) / 1024 / 1024).toFixed(1)} MB`;
      runBtn.disabled = fileQueue.length < 2;
    }
  } else {
    if (primaryFile) {
      dz.classList.add('hidden');
      wfContainer.style.display = 'block';
      qContainer.style.display = 'none';
      
      document.getElementById('meta-size').innerText = `${(primaryFile.size / 1024 / 1024).toFixed(1)} MB`;
      runBtn.disabled = false;
      
      initWavesurfer(primaryFile);
    } else {
      dz.classList.remove('hidden');
      wfContainer.style.display = 'none';
      runBtn.disabled = true;
    }
  }
}

window.removeFile = function(idx) {
  fileQueue.splice(idx, 1);
  updateFileUI();
};

window.moveFileUp = function(idx) {
  if (idx === 0) return;
  const temp = fileQueue[idx];
  fileQueue[idx] = fileQueue[idx - 1];
  fileQueue[idx - 1] = temp;
  updateFileUI();
};

window.moveFileDown = function(idx) {
  if (idx === fileQueue.length - 1) return;
  const temp = fileQueue[idx];
  fileQueue[idx] = fileQueue[idx + 1];
  fileQueue[idx + 1] = temp;
  updateFileUI();
};

window.queueWavesurfers = [];
window.queueRegions = [];
window.renderQueueTimeout = null;



// ── Multi-Track Timeline Engine ──
window.timelineState = {
  tracks: [], // { id, name, volume, mute, solo, clips: [] }
  zoom: 20 // pixels per second
};

window.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
window.timelineSources = [];

async function loadAudioBuffer(file) {
  if(file.audioBuffer) return file.audioBuffer;
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const buffer = await audioCtx.decodeAudioData(e.target.result);
        file.audioBuffer = buffer; resolve(buffer);
      } catch(err) {
        resolve(0);
      }
    };
    reader.readAsArrayBuffer(file);
  });
}


function drawWaveform(buffer, canvas, fileStart, duration) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  
  if(!buffer) return;
  const data = buffer.getChannelData(0);
  const sampleRate = buffer.sampleRate;
  
  const startIdx = Math.floor(fileStart * sampleRate);
  const endIdx = Math.floor((fileStart + duration) * sampleRate);
  const step = Math.ceil((endIdx - startIdx) / width);
  const amp = height / 2;
  
  ctx.fillStyle = 'var(--accent-cyan)';
  ctx.clearRect(0, 0, width, height);
  
  for(let i=0; i<width; i++) {
     let min = 1.0;
     let max = -1.0;
     for (let j=0; j<step; j++) {
        const val = data[startIdx + (i*step) + j];
        if(val !== undefined) {
           if (val < min) min = val;
           if (val > max) max = val;
        }
     }
     ctx.fillRect(i, amp + (min * amp), 1, Math.max(1, (max - min) * amp));
  }
}

window.renderTimeline = async function() {
  const headersContainer = document.getElementById('timeline-headers');
  const tracksContainer = document.getElementById('timeline-tracks-container');
  if(!headersContainer || !tracksContainer) return;
  
  headersContainer.innerHTML = '<div class="timeline-header-spacer"></div>';
  tracksContainer.innerHTML = '';
  
  // Initialize tracks for any newly dropped files
  for(let i=0; i<fileQueue.length; i++) {
    if(!fileQueue[i].timelineImported) {
      fileQueue[i].timelineImported = true;
      const buffer = await loadAudioBuffer(fileQueue[i]); const dur = buffer ? buffer.duration : 0;
      timelineState.tracks.push({
        id: 'trk_' + i + '_' + Date.now(),
        name: fileQueue[i].name,
        volume: 1, mute: false, solo: false,
        clips: [{
           id: 'clip_' + i + '_' + Date.now(),
           fileIdx: i,
           startOffset: (currentTool === 'merge' ? (timelineState.tracks.length * dur) : 0),
           duration: dur,
           fileStart: 0
        }]
      });
    }
  }

  let maxTime = 0;
  
  timelineState.tracks.forEach((track, trkIdx) => {
    // Header
    const th = document.createElement('div');
    th.className = 'timeline-track-header';
    th.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="font-size:0.8rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:120px;">${track.name}</div>
        <div>
          <button style="background:transparent; border:none; color:var(--text-muted); cursor:pointer; padding:2px;" onclick="playSingleTrack(${trkIdx})" title="Solo & Play"><i class="ph-fill ph-play"></i></button>
          <button style="background:transparent; border:none; color:var(--accent-red); cursor:pointer; padding:2px;" onclick="deleteTrack(${trkIdx})" title="Delete Track"><i class="ph ph-trash"></i></button>
        </div>
      </div>
      <div style="display:flex; gap:4px; margin-top:8px;">
        <button style="background:${track.mute ? 'var(--accent-red)' : 'rgba(255,255,255,0.1)'}; border:none; border-radius:4px; color:#fff; width:24px; height:24px; cursor:pointer; font-size:0.7rem;" onclick="toggleTrackMute(${trkIdx})">M</button>
        <button style="background:${track.solo ? 'var(--accent-cyan)' : 'rgba(255,255,255,0.1)'}; border:none; border-radius:4px; color:#000; width:24px; height:24px; cursor:pointer; font-size:0.7rem;" onclick="toggleTrackSolo(${trkIdx})">S</button>
        <input type="range" min="0" max="2" step="0.1" value="${track.volume}" style="width:60px;" onchange="setTrackVol(${trkIdx}, this.value)">
      </div>
    `;
    headersContainer.appendChild(th);
    
    // Lane
    const lane = document.createElement('div');
    lane.className = 'timeline-track-lane';
    lane.dataset.idx = trkIdx;
    
    track.clips.forEach((clip, cIdx) => {
      const clipDur = clip.duration;
      if (clip.startOffset + clipDur > maxTime) maxTime = clip.startOffset + clipDur;
      
      const clipEl = document.createElement('div');
      clipEl.className = 'timeline-clip';
      clipEl.style.left = (clip.startOffset * timelineState.zoom) + 'px';
      clipEl.style.width = (clipDur * timelineState.zoom) + 'px';
      clipEl.innerHTML = `<div style="padding:0 8px; font-size:0.75rem; color:#fff; white-space:nowrap; z-index:2; pointer-events:none;">${fileQueue[clip.fileIdx].name}</div>`;
      clipEl.title = "Drag to move. Alt+Click to Razor (slice) at mouse.";
      
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, clipDur * timelineState.zoom);
      canvas.height = 70;
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      canvas.style.position = 'absolute';
      canvas.style.top = '0';
      canvas.style.left = '0';
      canvas.style.pointerEvents = 'none';
      canvas.style.opacity = '0.5';
      clipEl.appendChild(canvas);
      
      setTimeout(() => {
        const buffer = fileQueue[clip.fileIdx].audioBuffer;
        if(buffer) drawWaveform(buffer, canvas, clip.fileStart, clip.duration);
      }, 0);

      
      // DOM Drag & Razor
      clipEl.onmousedown = (e) => {
        e.preventDefault();
        
        // Razor Slicing
        if(e.altKey) {
          const rect = clipEl.getBoundingClientRect();
          const clickX = e.clientX - rect.left;
          const sliceSec = clickX / timelineState.zoom;
          
          if(sliceSec > 0.5 && sliceSec < clip.duration - 0.5) {
             // Split!
             const newClip = {
               id: 'clip_' + Date.now(),
               fileIdx: clip.fileIdx,
               startOffset: clip.startOffset + sliceSec,
               duration: clip.duration - sliceSec,
               fileStart: clip.fileStart + sliceSec
             };
             clip.duration = sliceSec;
             ensurePlaybackStopped(); track.clips.push(newClip);
             renderTimeline();
          }
          return;
        }
        
        // Drag
        const startX = e.clientX;
        const startLeft = parseFloat(clipEl.style.left);
        
        const onMove = (ev) => {
          let newLeft = startLeft + (ev.clientX - startX);
          if(newLeft < 0) newLeft = 0;
          clipEl.style.left = newLeft + 'px';
        };
        
        const onUp = (ev) => {
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          const finalTime = parseFloat(clipEl.style.left) / timelineState.zoom;
          clip.startOffset = finalTime;
          renderTimeline(); // re-render to update bounds
        };
        
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      };
      
      lane.appendChild(clipEl);
    });
    
    tracksContainer.appendChild(lane);
  });
  
  tracksContainer.style.width = ((maxTime + 20) * timelineState.zoom) + 'px';
  drawRuler(maxTime + 20);
  
  // Sync vertical scroll between tracks and headers
  const wrapper = document.getElementById('timeline-tracks-wrapper');
  if(wrapper) {
    wrapper.onscroll = () => {
      headersContainer.scrollTop = wrapper.scrollTop;
    };
  }
};

function drawRuler(totalSecs) {
  const ruler = document.getElementById('timeline-ruler');
  if(!ruler) return;
  ruler.innerHTML = '';
  ruler.style.width = (totalSecs * timelineState.zoom) + 'px';
  
  for(let i=0; i<totalSecs; i++) {
    if(i % 5 === 0) {
      const tick = document.createElement('div');
      tick.style.position = 'absolute';
      tick.style.left = (i * timelineState.zoom) + 'px';
      tick.style.bottom = '0';
      tick.style.height = '100%';
      tick.style.borderLeft = '1px solid rgba(255,255,255,0.2)';
      tick.style.paddingLeft = '4px';
      tick.style.fontSize = '0.65rem';
      tick.style.color = 'var(--text-muted)';
      tick.innerText = i + 's';
      ruler.appendChild(tick);
    }
  }
}


function ensurePlaybackStopped() {
  if (window.isTimelinePlaying) toggleMasterPlay();
}

window.playSingleTrack = function(trkIdx) {
  // Solo this track and play
  timelineState.tracks.forEach((t, i) => t.solo = (i === trkIdx));
  renderTimeline();
  if(!window.isTimelinePlaying) {
     toggleMasterPlay();
  }
};

window.deleteTrack = function(trkIdx) {
  ensurePlaybackStopped(); timelineState.tracks.splice(trkIdx, 1);
  renderTimeline();
};

function updateLiveTimelineAudio() {
  if (!window.isTimelinePlaying) return;
  const anySolo = timelineState.tracks.some(t => t.solo);
  
  if (window.timelineSources) {
    window.timelineSources.forEach(s => {
       if (s.gain && s.track) {
          const shouldMute = s.track.mute || (anySolo && !s.track.solo);
          const targetVol = shouldMute ? 0 : s.track.volume;
          s.gain.gain.setTargetAtTime(targetVol, audioCtx.currentTime, 0.05);
       }
    });
  }
}

window.toggleTrackMute = function(idx) {
  timelineState.tracks[idx].mute = !timelineState.tracks[idx].mute;
  updateLiveTimelineAudio();
  renderTimeline();
};
window.toggleTrackSolo = function(idx) {
  timelineState.tracks[idx].solo = !timelineState.tracks[idx].solo;
  updateLiveTimelineAudio();
  renderTimeline();
};
window.setTrackVol = function(idx, val) {
  const v = parseFloat(val);
  timelineState.tracks[idx].volume = v;
  updateLiveTimelineAudio();
};

// Scheduler hook
// Scheduler hook
window.toggleMasterPlay = async function() {
  if (currentTool !== 'merge' && currentTool !== 'overlay') {
     return window.oldToggleMasterPlay();
  }
  
  const btn1 = document.getElementById('preview-mix-btn'); const btn2 = document.getElementById('master-play-btn');
  if(window.isTimelinePlaying) {
    // stop
    window.timelineSources.forEach(s => { try{ s.source.stop(); }catch(e){} });
    window.timelineSources = [];
    clearInterval(window.timelineInterval);
    if(btn1) btn1.innerHTML = '<i class="ph-fill ph-play"></i> Preview Mix'; if(btn2) btn2.innerHTML = '<i class="ph-fill ph-play"></i>';
    window.isTimelinePlaying = false;
  } else {
    // play
    if(btn1) btn1.innerHTML = '<i class="ph-fill ph-stop"></i> Stop'; if(btn2) btn2.innerHTML = '<i class="ph-fill ph-stop"></i>';
    window.isTimelinePlaying = true;
    
    // Check solo
    const anySolo = timelineState.tracks.some(t => t.solo);
    
    // Schedule all clips
    const t0 = audioCtx.currentTime;
    
    for (const track of timelineState.tracks) {
      if(track.mute) continue;
      if(anySolo && !track.solo) continue;
      
      for (const clip of track.clips) {
         const buffer = fileQueue[clip.fileIdx].audioBuffer;
         if(!buffer) continue;
         
         const source = audioCtx.createBufferSource();
         source.buffer = buffer;
         const gain = audioCtx.createGain();
         gain.gain.value = track.volume;
         
         source.connect(gain);
         gain.connect(audioCtx.destination);
         
         // start at `t0 + clip.startOffset`
         // play the chunk of buffer starting at `clip.fileStart`
         // for duration `clip.duration`
         source.start(t0 + clip.startOffset, clip.fileStart, clip.duration);
         window.timelineSources.push({source, gain, track});
      }
    }
    
    // Laser animation
    const laser = document.getElementById('timeline-laser');
    window.timelineInterval = setInterval(() => {
      const elapsed = audioCtx.currentTime - t0;
      if(laser) laser.style.left = (elapsed * timelineState.zoom) + 'px';
    }, 50);
  }
};


function renderQueue() {
  clearTimeout(window.renderQueueTimeout);
  const list = document.getElementById('queue-list');
  list.innerHTML = '';
  
  if (window.queueWavesurfers) {
    window.queueWavesurfers.forEach(ws => ws && ws.destroy());
    window.queueWavesurfers = [];
    window.queueRegions = [];
  }
  
  fileQueue.forEach((f, i) => {
    let badge = '';
    if (currentTool === 'overlay') {
      badge = i === 0 
        ? '<span style="background:var(--accent-cyan); color:#000; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold; margin-right:8px; vertical-align:middle;">BASE</span>' 
        : '<span style="background:#444; color:#fff; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold; margin-right:8px; vertical-align:middle;">OVERLAY</span>';
    } else if (currentTool === 'merge') {
      badge = `<span style="background:#444; color:#fff; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold; margin-right:8px; vertical-align:middle;">TRACK ${i+1}</span>`;
    }

    list.innerHTML += `
      <div class="queue-item">
        <div class="queue-info">
          <div style="display:flex; flex-direction:column; gap:8px; flex:1;">
            <div style="display:flex; justify-content:space-between;">
              <div class="queue-name" title="${f.name}">${badge}${f.name}</div>
              <div class="queue-meta">${(f.size/1024/1024).toFixed(1)} MB</div>
            </div>
            <div id="q-ws-${i}" style="width:100%; height:40px; background:rgba(255,255,255,0.02); border-radius:4px;"></div>
            <div style="display:flex; gap:8px;">
              <input type="number" step="0.5" class="input-text pro-scrub" style="padding:4px 8px; font-size:0.8rem; width:80px;" placeholder="dB" value="${f.customDb||'0'}" oninput="updateQueueMeta(${i}, 'customDb', this.value)" data-idx="${i}" data-field="customDb" data-type="number" title="Volume Gain (dB)" />
              <input type="text" class="input-text pro-scrub" style="padding:4px 8px; font-size:0.8rem; width:70px;" placeholder="Start" value="${f.customStart||''}" onchange="updateQueueMeta(${i}, 'customStart', this.value)" data-idx="${i}" data-field="customStart" data-type="time" title="Trim Start - Drag to scrub" />
              <input type="text" class="input-text pro-scrub" style="padding:4px 8px; font-size:0.8rem; width:70px;" placeholder="End" value="${f.customEnd||''}" onchange="updateQueueMeta(${i}, 'customEnd', this.value)" data-idx="${i}" data-field="customEnd" data-type="time" title="Trim End - Drag to scrub" />
            </div>
          </div>
        </div>
        <div style="display:flex; gap:4px; align-items:center; margin-left:16px;">
          <button class="queue-btn" onclick="previewSingleFile(${i})" title="Play/Stop Track"><i class="ph-fill ph-play" id="play-icon-${i}"></i></button>
          <button class="queue-btn" onclick="moveFileUp(${i})" title="Move Up" ${i===0?'disabled style="opacity:0.2"':''}><i class="ph ph-caret-up"></i></button>
          <button class="queue-btn" onclick="moveFileDown(${i})" title="Move Down" ${i===fileQueue.length-1?'disabled style="opacity:0.2"':''}><i class="ph ph-caret-down"></i></button>
          <button class="queue-btn danger" onclick="removeFile(${i})" title="Remove"><i class="ph ph-trash"></i></button>
        </div>
      </div>`;
  });
  
  // Initialize embedded wavesurfers
  window.renderQueueTimeout = setTimeout(() => {
    fileQueue.forEach((f, i) => {
      const ws = WaveSurfer.create({
        container: `#q-ws-${i}`,
        waveColor: 'rgba(255, 255, 255, 0.2)',
        progressColor: 'var(--accent-cyan)',
        height: 40,
        barWidth: 2,
        barRadius: 2,
        cursorWidth: 1,
        normalize: true,
        url: URL.createObjectURL(f)
      });
      
      const db = parseFloat(f.customDb || 0);
      ws.setVolume(Math.pow(10, db / 20));
      
      const wsRegions = ws.registerPlugin(WaveSurfer.Regions.create());
      window.queueRegions.push(wsRegions);
      
      ws.on('ready', () => {
         const s = parseTimeToSec(f.customStart) || 0;
         const e = parseTimeToSec(f.customEnd) || ws.getDuration();
         wsRegions.addRegion({
           id: 'trim',
           start: s,
           end: e,
           color: 'rgba(0, 229, 255, 0.2)',
           drag: true,
           resize: true
         });
      });
      
      wsRegions.on('region-updated', (region) => {
         if (region.id === 'trim') {
            const sFormat = formatTime(region.start);
            const eFormat = formatTime(region.end);
            fileQueue[i].customStart = sFormat;
            fileQueue[i].customEnd = eFormat;
            
            const itemDiv = document.querySelectorAll('.queue-item')[i];
            if (itemDiv) {
               const inputs = itemDiv.querySelectorAll('input[type="text"]');
               if (inputs.length >= 3) {
                 inputs[1].value = sFormat;
                 inputs[2].value = eFormat;
               }
            }
         }
      });
      
      wsRegions.on('region-clicked', (region, e) => {
         e.stopPropagation();
         region.play();
      });
      
      ws.on('play', () => {
        const icon = document.getElementById(`play-icon-${i}`);
        if(icon) icon.className = 'ph-fill ph-pause';
      });
      
      ws.on('pause', () => {
        const icon = document.getElementById(`play-icon-${i}`);
        if(icon) icon.className = 'ph-fill ph-play';
      });
      
      window.queueWavesurfers.push(ws);
    });
  }, 50);
}

window.updateQueueMeta = function(idx, field, value) {
  fileQueue[idx][field] = value;
  
  if (field === 'customDb') {
    const db = parseFloat(value || 0);
    const gainVal = Math.pow(10, db / 20);
    
    if (window.queueWavesurfers && window.queueWavesurfers[idx]) {
      window.queueWavesurfers[idx].setVolume(gainVal);
    }
    
    if (masterPlayState && masterAudioNodes) {
      masterAudioNodes.forEach(node => {
        if (node.idx === idx && node.gainNode) {
          node.gainNode.gain.value = gainVal;
        }
      });
    }
  }
  
  if ((field === 'customStart' || field === 'customEnd') && window.queueRegions && window.queueRegions[idx]) {
    const regs = window.queueRegions[idx].getRegions();
    if(regs.length > 0) {
       const ws = window.queueWavesurfers[idx];
       const s = parseTimeToSec(fileQueue[idx].customStart) || 0;
       const e = parseTimeToSec(fileQueue[idx].customEnd) || ws.getDuration();
       regs[0].setOptions({ start: s, end: e });
    }
  }
};

// ── Master Preview HUD & Logic ──
let multiPreviewCtx = null;
let masterPlayState = false;
let masterPauseTime = 0;
let masterDuration = 0;
let masterRaf = null;
let masterGainNode = null;
let masterAudioNodes = [];
let masterStartTime = 0;

window.updateMasterVolume = function() {
  const vol = document.getElementById('master-vol').value;
  if (masterGainNode) {
    masterGainNode.gain.value = vol / 100;
  }
};

window.oldToggleMasterPlay = function() {
  if (masterPlayState) {
    pauseMaster();
  } else {
    document.getElementById('queue-container').classList.add('preview-active');
    
    // Always rebuild to pick up any changes from the input boxes!
    if (multiPreviewCtx) {
      multiPreviewCtx.close();
      multiPreviewCtx = null;
    }
    
    buildMasterGraph(masterPauseTime);
  }
};

function pauseMaster() {
  masterPlayState = false;
  if (multiPreviewCtx) {
    masterPauseTime = masterPauseTime + (multiPreviewCtx.currentTime - masterStartTime);
    multiPreviewCtx.suspend();
  }
  document.getElementById('master-play-btn').innerHTML = '<i class="ph-fill ph-play"></i>';
  cancelAnimationFrame(masterRaf);
}

function resumeMaster() {
  masterPlayState = true;
  masterStartTime = multiPreviewCtx.currentTime;
  multiPreviewCtx.resume();
  document.getElementById('master-play-btn').innerHTML = '<i class="ph-fill ph-pause"></i>';
  loopMaster();
}

function stopMaster() {
  masterPlayState = false;
  masterPauseTime = 0;
  cancelAnimationFrame(masterRaf);
  if (multiPreviewCtx) { multiPreviewCtx.close(); }
  multiPreviewCtx = null;
  masterAudioNodes = [];
  document.getElementById('master-play-btn').innerHTML = '<i class="ph-fill ph-play"></i>';
  document.getElementById('hud-progress').style.width = '0%';
  document.getElementById('hud-laser').style.left = '0%';
  document.getElementById('hud-time-current').innerText = '0:00';
  document.getElementById('queue-container').classList.remove('preview-active');
}

let isMasterScrubbing = false;

window.startMasterScrub = function(e) {
  if (!masterDuration) return;
  isMasterScrubbing = true;
  document.body.style.cursor = 'ew-resize';
  doMasterScrub(e);
};

function doMasterScrub(e) {
  if (!masterDuration) return;
  const scrubber = document.getElementById('hud-scrubber');
  const rect = scrubber.getBoundingClientRect();
  const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  masterPauseTime = percent * masterDuration;
  
  document.getElementById('hud-progress').style.width = `${percent * 100}%`;
  document.getElementById('hud-laser').style.left = `${percent * 100}%`;
  document.getElementById('hud-time-current').innerText = formatTime(masterPauseTime);
  
  // Sync individual waveforms while dragging (visual preview only)
  window.queueWavesurfers.forEach((ws, i) => {
      if(!ws) return;
      const f = fileQueue[i];
      const startSec = parseTimeToSec(f.customStart) || 0;
      const endSec = parseTimeToSec(f.customEnd) || ws.getDuration();
      
      let trackGlobalStart = 0;
      if (currentTool === 'merge') {
          for(let j=0; j<i; j++) {
              trackGlobalStart += (parseTimeToSec(fileQueue[j].customEnd) || window.queueWavesurfers[j].getDuration()) - (parseTimeToSec(fileQueue[j].customStart) || 0);
          }
      }
      const trackGlobalEnd = trackGlobalStart + (endSec - startSec);
      if (masterPauseTime >= trackGlobalStart && masterPauseTime <= trackGlobalEnd) {
          const localTime = startSec + (masterPauseTime - trackGlobalStart);
          ws.setTime(localTime);
      }
  });
  
  if (masterPlayState) {
     if (multiPreviewCtx) { multiPreviewCtx.close(); multiPreviewCtx = null; }
     masterAudioNodes = [];
     cancelAnimationFrame(masterRaf);
  }
}

document.addEventListener('mousemove', (e) => {
  if (isMasterScrubbing) {
     doMasterScrub(e);
     e.preventDefault();
  }
});

document.addEventListener('mouseup', (e) => {
  if (isMasterScrubbing) {
     isMasterScrubbing = false;
     document.body.style.cursor = '';
     if (masterPlayState) {
         buildMasterGraph(masterPauseTime);
     }
  }
});

async function buildMasterGraph(startTimeOffset = 0) {
  if (!fileQueue || fileQueue.length === 0) return;
  
  multiPreviewCtx = new (window.AudioContext || window.webkitAudioContext)();
  masterGainNode = multiPreviewCtx.createGain();
  masterGainNode.gain.value = document.getElementById('master-vol').value / 100;
  masterGainNode.connect(multiPreviewCtx.destination);
  
  masterPlayState = true;
  document.getElementById('master-play-btn').innerHTML = '<i class="ph ph-spinner ph-spin"></i>';
  
  try {
    let offset = 0;
    masterDuration = 0;
    
    let trackConfigs = [];
    for (let i = 0; i < fileQueue.length; i++) {
      const f = fileQueue[i];
      const arrayBuffer = await f.arrayBuffer();
      const audioBuffer = await multiPreviewCtx.decodeAudioData(arrayBuffer);
      
      const startSec = parseTimeToSec(f.customStart) || 0;
      const endSec = parseTimeToSec(f.customEnd) || audioBuffer.duration;
      const durSec = endSec - startSec;
      
      trackConfigs.push({
        buffer: audioBuffer,
        db: parseFloat(f.customDb || 0),
        startSec, durSec,
        globalStart: currentTool === 'merge' ? offset : 0,
        idx: i
      });
      
      if (currentTool === 'merge') offset += durSec;
      else masterDuration = Math.max(masterDuration, durSec);
    }
    
    if (currentTool === 'merge') masterDuration = offset;
    document.getElementById('hud-time-total').innerText = formatTime(masterDuration);
    
    if (startTimeOffset >= masterDuration) {
       stopMaster();
       return;
    }
    
    masterAudioNodes = [];
    trackConfigs.forEach(tc => {
       const trackEnd = tc.globalStart + tc.durSec;
       if (startTimeOffset < trackEnd) {
           const source = multiPreviewCtx.createBufferSource();
           source.buffer = tc.buffer;
           
           const gainNode = multiPreviewCtx.createGain();
           gainNode.gain.value = Math.pow(10, tc.db / 20);
           
           source.connect(gainNode);
           gainNode.connect(masterGainNode);
           
           let playStart = tc.startSec;
           let delay = tc.globalStart - startTimeOffset;
           
           if (delay < 0) {
               playStart += Math.abs(delay);
               delay = 0;
           }
           
           source.start(multiPreviewCtx.currentTime + delay, playStart);
           masterAudioNodes.push({ source, gainNode, idx: tc.idx });
       }
    });
    
    masterStartTime = multiPreviewCtx.currentTime;
    document.getElementById('master-play-btn').innerHTML = '<i class="ph-fill ph-pause"></i>';
    loopMaster();
    
    const longestNode = masterAudioNodes.reduce((prev, curr) => (prev && prev.source.buffer.duration > curr.source.buffer.duration) ? prev : curr, masterAudioNodes[0]);
    if (longestNode) {
       longestNode.source.onended = () => {
           if (masterPlayState && (masterPauseTime + (multiPreviewCtx.currentTime - masterStartTime)) >= masterDuration - 0.1) {
               stopMaster();
           }
       };
    }
    
  } catch (err) {
    showToast("Error generating preview", "error");
    stopMaster();
  }
}

function loopMaster() {
  if (!masterPlayState) return;
  const current = masterPauseTime + (multiPreviewCtx.currentTime - masterStartTime);
  
  if (current >= masterDuration) {
      stopMaster();
      return;
  }
  
  const percent = Math.min(1, current / masterDuration);
  document.getElementById('hud-progress').style.width = `${percent * 100}%`;
  document.getElementById('hud-laser').style.left = `${percent * 100}%`;
  document.getElementById('hud-time-current').innerText = formatTime(current);
  
  // Sync individual waveforms
  window.queueWavesurfers.forEach((ws, i) => {
      if(!ws) return;
      const f = fileQueue[i];
      const startSec = parseTimeToSec(f.customStart) || 0;
      const endSec = parseTimeToSec(f.customEnd) || ws.getDuration();
      
      let trackGlobalStart = 0;
      if (currentTool === 'merge') {
          for(let j=0; j<i; j++) {
              trackGlobalStart += (parseTimeToSec(fileQueue[j].customEnd) || window.queueWavesurfers[j].getDuration()) - (parseTimeToSec(fileQueue[j].customStart) || 0);
          }
      }
      
      const trackGlobalEnd = trackGlobalStart + (endSec - startSec);
      
      if (current >= trackGlobalStart && current <= trackGlobalEnd) {
          const localTime = startSec + (current - trackGlobalStart);
          ws.setTime(localTime);
      }
  });
  
  masterRaf = requestAnimationFrame(loopMaster);
}

function parseTimeToSec(t) {
  if (!t) return null;
  if (t.includes(':')) {
    const parts = t.split(':');
    return parseInt(parts[0])*60 + parseFloat(parts[1]);
  }
  return parseFloat(t);
}

window.previewSingleFile = function(idx) {
  if (window.queueWavesurfers && window.queueWavesurfers[idx]) {
    window.queueWavesurfers[idx].playPause();
  }
};

// ── Wavesurfer ──
function initWavesurfer(file) {
  const container = document.getElementById('waveform');
  if (wavesurfer) {
    wavesurfer.destroy();
  }
  container.innerHTML = '';
  
  wavesurfer = WaveSurfer.create({
    container: '#waveform',
    waveColor: 'rgba(0, 229, 255, 0.4)',
    progressColor: '#00E5FF',
    cursorColor: '#FFFFFF',
    barWidth: 2,
    barRadius: 2,
    cursorWidth: 2,
    height: 160,
    normalize: true
  });
  
  const url = URL.createObjectURL(file);
  wavesurfer.load(url);
  
  const timeEl = document.getElementById('ws-time');
  const playBtn = document.getElementById('ws-play-btn');
  
  const updateTime = () => {
    const curr = wavesurfer.getCurrentTime();
    const dur = wavesurfer.getDuration();
    timeEl.innerText = `${formatTime(curr)} / ${formatTime(dur)}`;
  };

  wavesurfer.on('ready', () => {
    document.getElementById('meta-duration').innerText = formatTime(wavesurfer.getDuration());
    updateTime();
    
    if (currentTool === 'crop' || currentTool === 'extract') {
      const mainRegions = wavesurfer.registerPlugin(WaveSurfer.Regions.create());
      
      let sInput, eInput;
      if (currentTool === 'crop') {
         sInput = document.querySelector('#insp-crop input[name="start"]');
         eInput = document.querySelector('#insp-crop input[name="end"]');
      } else {
         sInput = document.querySelector('#insp-extract input[name="start"]');
         eInput = document.querySelector('#insp-extract input[name="end"]');
      }
      
      let s = 0;
      let e = wavesurfer.getDuration();
      if (sInput && sInput.value) s = parseTimeToSec(sInput.value) || 0;
      if (eInput && eInput.value) e = parseTimeToSec(eInput.value) || wavesurfer.getDuration();
      
      mainRegions.addRegion({
        id: 'trim',
        start: s,
        end: e,
        color: 'rgba(0, 229, 255, 0.2)',
        drag: true,
        resize: true
      });
      
      mainRegions.on('region-updated', (region) => {
         if (sInput) sInput.value = formatTime(region.start);
         if (eInput) eInput.value = formatTime(region.end);
      });
      
      mainRegions.on('region-clicked', (region, e) => {
         e.stopPropagation();
         region.play();
      });
      
      const updateRegion = () => {
         const regs = mainRegions.getRegions();
         if(regs.length > 0) {
            regs[0].setOptions({
               start: parseTimeToSec(sInput.value) || 0,
               end: parseTimeToSec(eInput.value) || wavesurfer.getDuration()
            });
         }
      };
      
      if (sInput) sInput.addEventListener('change', updateRegion);
      if (eInput) eInput.addEventListener('change', updateRegion);
    }
  });
  
  wavesurfer.on('audioprocess', () => {
    updateTime();
    if (currentTool === 'crop' || currentTool === 'extract') {
       const sInput = document.querySelector(currentTool === 'crop' ? '#insp-crop input[name="end"]' : '#insp-extract input[name="end"]');
       if (sInput && sInput.value) {
          const end = parseTimeToSec(sInput.value);
          if (end && wavesurfer.getCurrentTime() >= end) {
             wavesurfer.pause();
          }
       }
    }
  });
  wavesurfer.on('seek', updateTime);
  
  // Clean up old event listeners by cloning the button
  const newPlayBtn = playBtn.cloneNode(true);
  playBtn.parentNode.replaceChild(newPlayBtn, playBtn);
  
  newPlayBtn.addEventListener('click', () => {
    wavesurfer.playPause();
  });
  
  wavesurfer.on('play', () => newPlayBtn.innerHTML = '<i class="ph-fill ph-pause"></i>');
  wavesurfer.on('pause', () => newPlayBtn.innerHTML = '<i class="ph-fill ph-play"></i>');
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(2);
  return `${m}:${s.padStart(5, '0')}`;
}

// ── Output Wavesurfer ──
function initOutputWavesurfer(url) {
  document.getElementById('result-container').style.display = 'block';
  const container = document.getElementById('waveform-out');
  if (wsOut) wsOut.destroy();
  container.innerHTML = '';
  
  wsOut = WaveSurfer.create({
    container: '#waveform-out',
    waveColor: 'rgba(0, 245, 139, 0.4)',
    progressColor: '#00F58B',
    cursorColor: '#FFFFFF',
    barWidth: 2,
    barRadius: 2,
    cursorWidth: 2,
    height: 100,
    normalize: true
  });
  
  wsOut.load(url);
  
  const timeEl = document.getElementById('ws-out-time');
  const playBtn = document.getElementById('ws-out-play-btn');
  const dlBtn = document.getElementById('result-download-btn');
  
  dlBtn.href = url;
  
  const updateTime = () => {
    const curr = wsOut.getCurrentTime();
    const dur = wsOut.getDuration();
    timeEl.innerText = `${formatTime(curr)} / ${formatTime(dur)}`;
  };

  wsOut.on('ready', updateTime);
  wsOut.on('audioprocess', updateTime);
  wsOut.on('seek', updateTime);
  
  const newPlayBtn = playBtn.cloneNode(true);
  playBtn.parentNode.replaceChild(newPlayBtn, playBtn);
  
  newPlayBtn.addEventListener('click', () => wsOut.playPause());
  
  wsOut.on('play', () => newPlayBtn.innerHTML = '<i class="ph-fill ph-pause"></i>');
  wsOut.on('pause', () => newPlayBtn.innerHTML = '<i class="ph-fill ph-play"></i>');
}

// ── Execution ──
document.getElementById('run-btn').addEventListener('click', async () => {
  const config = TOOLS[currentTool];
  
  if (!config.hideDropzone && !primaryFile && !config.multi) {
    showToast('Please upload an audio file first', 'error');
    return;
  }
  
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.innerHTML = `<i class="ph ph-spinner ph-spin"></i> Processing...`;
  
  try {
    if (currentTool === 'merge' || currentTool === 'overlay') {
       return await exportTimeline();
    }
    
    const fd = new FormData();
    
    if (!config.hideDropzone) {
      if (config.multi) {
        if (fileQueue.length < 2) return showToast('Add at least 2 files.', 'error');
        
        if (currentTool === 'overlay') {
          fd.append('base', fileQueue[0]);
          fileQueue.slice(1).forEach(f => fd.append('overlays', f));
        } else {
          fileQueue.forEach(f => fd.append('files', f));
        }
        
        const meta = fileQueue.map(f => ({
          db: f.customDb || 0,
          start: f.customStart || "",
          end: f.customEnd || ""
        }));
        fd.append('metadata', JSON.stringify(meta));
      } else if (primaryFile) {
        fd.append('file', primaryFile);
      }
    }
    
    // Append tool specific inputs from inspector
    const insp = document.getElementById(`insp-${currentTool}`);
    if (insp) {
      insp.querySelectorAll('input, select').forEach(el => {
        if (el.type === 'checkbox') fd.append(el.name, el.checked);
        else fd.append(el.name, el.value);
      });
    }
    
    if (currentTool === 'batch') {
      const op = document.getElementById('batch_op').value;
      let completed = 0;
      for (let i = 0; i < fileQueue.length; i++) {
        btn.innerHTML = `<i class="ph ph-spinner ph-spin"></i> Processing ${i+1} / ${fileQueue.length}...`;
        const bFd = new FormData();
        bFd.append('file', fileQueue[i]);
        if (op === 'convert') bFd.append('format', 'mp3');
        
        try {
          const res = await fetch(`/api/${op}`, { method: 'POST', body: bFd });
          const j = await res.json();
          if (res.ok && j.url) {
            const a = document.createElement('a');
            a.href = j.url;
            a.download = '';
            a.click();
            completed++;
          }
        } catch(e) {
          showToast(`Error processing ${fileQueue[i].name}: ${e.message}`, 'error');
        }
      }
      showToast(`Batch finished! ${completed} files mastered.`, 'success');
      btn.innerHTML = origHtml;
      btn.disabled = false;
      return;
    }

    const res = await fetch(`/api/${currentTool}`, { method: 'POST', body: fd });
    const j = await res.json();
    
    if (!j.ok) throw new Error(j.error);
    
    if (config.text) {
      document.getElementById('transText').value = j.text;
      document.getElementById('transcribe-output').style.display = 'block';
      const a = document.createElement('a');
      a.href = j.url;
      a.download = '';
      a.click();
      if (j.srt_url) {
        setTimeout(() => {
          const a2 = document.createElement('a');
          a2.href = j.srt_url;
          a2.download = '';
          a2.click();
        }, 500);
      }
      showToast('Transcription & Subtitles saved!', 'success');
    } else {
      initOutputWavesurfer(j.url);
      showToast('Audio processed successfully', 'success', `Duration: ${j.duration_str}`);
    }
    
    // Clear the input queue/file after a successful task so it doesn't accumulate
    primaryFile = null;
    fileQueue = [];
    updateFileUI();
    
  } catch(e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="ph ph-play"></i> Process Audio`;
  }
});

// ── Toasts ──
function showToast(msg, type='success', sub='') {
  const tc = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icon = type === 'error' ? 'ph-warning-circle' : 'ph-check-circle';
  t.innerHTML = `
    <i class="ph ${icon}" style="font-size: 1.5rem;"></i>
    <div class="toast-content">
      <div class="toast-title">${type === 'error' ? 'Error' : 'Success'}</div>
      <div class="toast-msg">${msg}</div>
      ${sub ? `<div class="toast-msg">${sub}</div>` : ''}
    </div>
  `;
  tc.appendChild(t);
  setTimeout(() => {
    t.classList.add('hiding');
    setTimeout(() => t.remove(), 300);
  }, 4000);
}

window.savePreset = function() {
  const inputs = document.querySelectorAll('#inspector input, #inspector select');
  const data = {};
  inputs.forEach(el => {
    if (el.name) data[el.name] = el.value;
  });
  localStorage.setItem('aryan_audio_preset', JSON.stringify(data));
  showToast('Settings saved as Global Preset!', 'success');
};

window.loadPreset = function() {
  const str = localStorage.getItem('aryan_audio_preset');
  if (!str) {
    showToast('No preset found', 'error');
    return;
  }
  const data = JSON.parse(str);
  Object.keys(data).forEach(k => {
    const el = document.querySelector(`[name="${k}"]`);
    if (el) el.value = data[k];
  });
  showToast('Global Preset loaded!', 'success');
};

// ── Client-Side Timeline Rendering (OfflineAudioContext) ──
window.exportTimeline = async function() {
  const btn = document.getElementById('run-btn');
  btn.innerHTML = `<i class="ph ph-spinner ph-spin"></i> Rendering Mix...`;
  
  let maxTime = 0;
  timelineState.tracks.forEach(t => {
     if(t.mute) return;
     t.clips.forEach(c => {
       if (c.startOffset + c.duration > maxTime) maxTime = c.startOffset + c.duration;
     });
  });
  
  if (maxTime === 0) {
    showToast('Timeline is empty or muted.', 'error');
    btn.innerHTML = 'Run Engine'; btn.disabled = false;
    return;
  }
  
  const sampleRate = audioCtx.sampleRate;
  const offlineCtx = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(2, sampleRate * maxTime, sampleRate);
  
  for (const track of timelineState.tracks) {
    if(track.mute) continue;
    for (const clip of track.clips) {
       const buffer = fileQueue[clip.fileIdx].audioBuffer;
       if(!buffer) continue;
       
       const source = offlineCtx.createBufferSource();
       source.buffer = buffer;
       const gain = offlineCtx.createGain();
       gain.gain.value = track.volume;
       
       source.connect(gain);
       gain.connect(offlineCtx.destination);
       
       source.start(clip.startOffset, clip.fileStart, clip.duration);
    }
  }
  
  try {
    const renderedBuffer = await offlineCtx.startRendering();
    const wavBlob = audioBufferToWav(renderedBuffer);
    const wavFile = new File([wavBlob], "master_mix.wav", { type: 'audio/wav' });
    
    btn.innerHTML = `<i class="ph ph-spinner ph-spin"></i> Encoding to MP3...`;
    
    const fd = new FormData();
    fd.append('file', wavFile);
    fd.append('format', 'mp3');
    fd.append('bitrate', '320k');
    
    const res = await fetch('/api/convert', { method: 'POST', body: fd });
    const data = await res.json();
    
    // Generate Systematic Naming
    let trackNames = timelineState.tracks
      .filter(t => !t.mute && t.clips.length > 0)
      .map(t => (t.name.split('.').slice(0, -1).join('.') || t.name).replace(/[^a-zA-Z0-9]/g, ''));
      
    let mixName = "Empty";
    if (trackNames.length > 0 && trackNames.length <= 2) mixName = trackNames.join('_');
    else if (trackNames.length > 2) mixName = trackNames.slice(0, 2).join('_') + `_and_${trackNames.length - 2}_more`;
    
    const d = new Date();
    const ts = `${d.getFullYear()}${(d.getMonth()+1).toString().padStart(2,'0')}${d.getDate().toString().padStart(2,'0')}_${d.getHours().toString().padStart(2,'0')}${d.getMinutes().toString().padStart(2,'0')}`;
    const toolPrefix = currentTool === 'merge' ? 'Merge' : (currentTool === 'overlay' ? 'Mix' : 'Render');
    const finalDownloadName = `Kronos_${toolPrefix}_${mixName}_${ts}.mp3`;
    
    if (data.status === 'success') {
      document.getElementById('result-download-btn').href = data.url;
      document.getElementById('result-download-btn').download = finalDownloadName;
      initOutputWavesurfer(data.url);
      showToast('Mix rendered to MP3 successfully!', 'success');
    } else {
      showToast(data.msg || 'Encoding failed', 'error');
    }
  } catch(err) {
    showToast('Rendering failed: ' + err.message, 'error');
  }
  
  btn.innerHTML = '<i class="ph ph-play"></i> Process Audio';
  btn.disabled = false;
};

function audioBufferToWav(buffer, opt) {
  opt = opt || {};
  var numChannels = buffer.numberOfChannels;
  var sampleRate = buffer.sampleRate;
  var format = opt.float32 ? 3 : 1;
  var bitDepth = format === 3 ? 32 : 16;
  var result;
  if (numChannels === 2) {
    result = interleave(buffer.getChannelData(0), buffer.getChannelData(1));
  } else {
    result = buffer.getChannelData(0);
  }
  return encodeWAV(result, format, sampleRate, numChannels, bitDepth);
}
function interleave(inputL, inputR) {
  var length = inputL.length + inputR.length;
  var result = new Float32Array(length);
  var index = 0, inputIndex = 0;
  while (index < length) {
    result[index++] = inputL[inputIndex];
    result[index++] = inputR[inputIndex];
    inputIndex++;
  }
  return result;
}
function encodeWAV(samples, format, sampleRate, numChannels, bitDepth) {
  var bytesPerSample = bitDepth / 8;
  var blockAlign = numChannels * bytesPerSample;
  var buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  var view = new DataView(buffer);
  function writeString(view, offset, string) {
    for (var i = 0; i < string.length; i++) view.setUint8(offset + i, string.charCodeAt(i));
  }
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, format, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitDepth, true);
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * bytesPerSample, true);
  if (format === 1) {
    var offset = 44;
    for (var i = 0; i < samples.length; i++, offset += 2) {
      var s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
  } else {
    var offset = 44;
    for (var i = 0; i < samples.length; i++, offset += 4) {
      view.setFloat32(offset, samples[i], true);
    }
  }
  return new Blob([buffer], { type: 'audio/wav' });
};

// ── Pro-Scrub Inputs ──
let isScrubbingInput = false;
let scrubStartVal = 0;
let scrubStartX = 0;
let scrubInput = null;
let hasScrubbed = false;

document.addEventListener('mousedown', (e) => {
  if (e.target.classList.contains('pro-scrub')) {
    isScrubbingInput = true;
    hasScrubbed = false;
    scrubInput = e.target;
    scrubStartX = e.clientX;
    
    if (scrubInput.dataset.type === 'time') {
      scrubStartVal = parseTimeToSec(scrubInput.value) || 0;
    } else {
      scrubStartVal = parseFloat(scrubInput.value) || 0;
    }
  }
});

document.addEventListener('mousemove', (e) => {
  if (!isScrubbingInput || !scrubInput) return;
  const deltaX = e.clientX - scrubStartX;
  
  if (Math.abs(deltaX) > 2) {
    if (!hasScrubbed) {
      hasScrubbed = true;
      document.body.style.userSelect = 'none';
    }
    
    let newVal;
    if (scrubInput.dataset.type === 'time') {
      newVal = Math.max(0, scrubStartVal + (deltaX * 0.1));
      scrubInput.value = formatTime(newVal);
    } else {
      newVal = scrubStartVal + (deltaX * 0.1);
      scrubInput.value = newVal.toFixed(1);
    }
    
    const idx = parseInt(scrubInput.dataset.idx);
    const field = scrubInput.dataset.field;
    updateQueueMeta(idx, field, scrubInput.value);
  }
});

document.addEventListener('mouseup', () => {
  if (isScrubbingInput) {
    isScrubbingInput = false;
    scrubInput = null;
    document.body.style.userSelect = '';
  }
});

// ── Theme Management ──
window.setTheme = function(val) {
  document.documentElement.setAttribute('data-theme', val);
  localStorage.setItem('aryan_theme', val);
  document.querySelectorAll('.theme-swatch').forEach(btn => {
     btn.classList.toggle('active', btn.dataset.value === val);
  });
  setTimeout(() => {
     const c = getComputedStyle(document.documentElement).getPropertyValue('--bg-surface').trim();
     const meta = document.getElementById('theme-color-meta');
     if (meta) meta.setAttribute('content', c);
  }, 50);
};

document.addEventListener('DOMContentLoaded', () => {
  const t = localStorage.getItem('aryan_theme') || 'dark';
  setTheme(t);
});
