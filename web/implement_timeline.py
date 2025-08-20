import re
import os

app_js = "./web/static/js/app.js"
with open(app_js, "r") as f:
    code = f.read()

# 1. Update updateFileUI to call renderTimeline instead of renderQueue
code = code.replace("renderQueue();", "if(currentTool==='merge'||currentTool==='overlay'){ renderTimeline(); } else { renderQueue(); }")

# 2. Add renderTimeline and Master Scheduler logic
timeline_code = """
// ── Multi-Track Timeline Engine ──
window.timelineState = {
  tracks: [], // { id, file, duration, startOffset, volume, mute, solo }
  zoom: 20 // pixels per second
};

window.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
window.timelineSources = [];

async function getAudioDuration(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const buffer = await audioCtx.decodeAudioData(e.target.result);
        resolve(buffer.duration);
      } catch(err) {
        resolve(0);
      }
    };
    reader.readAsArrayBuffer(file);
  });
}

window.renderTimeline = async function() {
  const headersContainer = document.getElementById('timeline-headers');
  const tracksContainer = document.getElementById('timeline-tracks-container');
  if(!headersContainer || !tracksContainer) return;
  
  headersContainer.innerHTML = '<div class="timeline-header-spacer"></div>';
  tracksContainer.innerHTML = '';
  
  // Sync state with fileQueue
  if(timelineState.tracks.length !== fileQueue.length) {
    for(let i=0; i<fileQueue.length; i++) {
      if(!timelineState.tracks[i]) {
        const dur = await getAudioDuration(fileQueue[i]);
        timelineState.tracks.push({
          id: 'trk_' + Date.now() + i,
          fileIdx: i,
          name: fileQueue[i].name,
          duration: dur,
          startOffset: (currentTool === 'merge' ? (i * dur) : 0),
          volume: 1, mute: false, solo: false
        });
      }
    }
  }

  let maxTime = 0;
  
  timelineState.tracks.forEach((track, idx) => {
    // Header
    const th = document.createElement('div');
    th.className = 'timeline-track-header';
    th.innerHTML = `
      <div style="font-size:0.8rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${track.name}</div>
      <div style="display:flex; gap:4px; margin-top:8px;">
        <button style="background:${track.mute ? 'var(--accent-red)' : 'rgba(255,255,255,0.1)'}; border:none; border-radius:4px; color:#fff; width:24px; height:24px; cursor:pointer; font-size:0.7rem;" onclick="toggleTrackMute(${idx})">M</button>
        <button style="background:${track.solo ? 'var(--accent-cyan)' : 'rgba(255,255,255,0.1)'}; border:none; border-radius:4px; color:#000; width:24px; height:24px; cursor:pointer; font-size:0.7rem;" onclick="toggleTrackSolo(${idx})">S</button>
        <input type="range" min="0" max="2" step="0.1" value="${track.volume}" style="width:60px;" onchange="setTrackVol(${idx}, this.value)">
      </div>
    `;
    headersContainer.appendChild(th);
    
    // Lane
    const lane = document.createElement('div');
    lane.className = 'timeline-track-lane';
    lane.dataset.idx = idx;
    
    // Clip
    const clipDur = track.duration;
    if (track.startOffset + clipDur > maxTime) maxTime = track.startOffset + clipDur;
    
    const clip = document.createElement('div');
    clip.className = 'timeline-clip';
    clip.style.left = (track.startOffset * timelineState.zoom) + 'px';
    clip.style.width = (clipDur * timelineState.zoom) + 'px';
    clip.innerHTML = `<div style="padding:0 8px; font-size:0.75rem; color:#fff; white-space:nowrap; z-index:2; pointer-events:none;">${track.name}</div>`;
    
    // DOM Drag logic for clip
    clip.onmousedown = (e) => {
      e.preventDefault();
      const startX = e.clientX;
      const startLeft = parseFloat(clip.style.left);
      
      const onMove = (ev) => {
        let newLeft = startLeft + (ev.clientX - startX);
        if(newLeft < 0) newLeft = 0;
        clip.style.left = newLeft + 'px';
      };
      
      const onUp = (ev) => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        const finalTime = parseFloat(clip.style.left) / timelineState.zoom;
        track.startOffset = finalTime;
        renderTimeline(); // re-render to update ruler bounds
      };
      
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    };
    
    lane.appendChild(clip);
    tracksContainer.appendChild(lane);
  });
  
  tracksContainer.style.width = ((maxTime + 20) * timelineState.zoom) + 'px';
  drawRuler(maxTime + 20);
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

window.toggleTrackMute = function(idx) {
  timelineState.tracks[idx].mute = !timelineState.tracks[idx].mute;
  renderTimeline();
};
window.toggleTrackSolo = function(idx) {
  timelineState.tracks[idx].solo = !timelineState.tracks[idx].solo;
  renderTimeline();
};
window.setTrackVol = function(idx, val) {
  timelineState.tracks[idx].volume = parseFloat(val);
};

// Scheduler hook
const oldToggleMasterPlay = window.toggleMasterPlay;
window.toggleMasterPlay = async function() {
  if (currentTool !== 'merge' && currentTool !== 'overlay') {
     return oldToggleMasterPlay();
  }
  
  const btn = document.getElementById('master-play-btn');
  if(window.isTimelinePlaying) {
    // stop
    window.timelineSources.forEach(s => { try{ s.source.stop(); }catch(e){} });
    window.timelineSources = [];
    clearInterval(window.timelineInterval);
    btn.innerHTML = '<i class="ph-fill ph-play"></i>';
    window.isTimelinePlaying = false;
  } else {
    // play
    btn.innerHTML = '<i class="ph-fill ph-stop"></i>';
    window.isTimelinePlaying = true;
    
    // Schedule all tracks
    const t0 = audioCtx.currentTime;
    timelineState.tracks.forEach(async track => {
      if(track.mute) return;
      const file = fileQueue[track.fileIdx];
      const buffer = await new Promise(r => {
        const reader = new FileReader();
        reader.onload = async (e) => r(await audioCtx.decodeAudioData(e.target.result));
        reader.readAsArrayBuffer(file);
      });
      
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      const gain = audioCtx.createGain();
      gain.gain.value = track.volume;
      
      source.connect(gain);
      gain.connect(audioCtx.destination);
      
      source.start(t0 + track.startOffset);
      window.timelineSources.push({source, gain});
    });
    
    // Laser animation
    const laser = document.getElementById('timeline-laser');
    window.timelineInterval = setInterval(() => {
      const elapsed = audioCtx.currentTime - t0;
      if(laser) laser.style.left = (elapsed * timelineState.zoom) + 'px';
    }, 50);
  }
};
"""

code = code.replace("function renderQueue() {", timeline_code + "\nfunction renderQueue() {")

with open(app_js, "w") as f:
    f.write(code)

print("Timeline injected successfully")
