import re

app_js = "./web/static/js/app.js"
with open(app_js, "r") as f:
    code = f.read()

# Replace the quick timeline code with a more robust Track/Clip architecture

start_marker = "// ── Multi-Track Timeline Engine ──"
end_marker = "function renderQueue() {"

pre = code[:code.find(start_marker)]
post = code[code.find(end_marker):]

advanced_timeline = """
// ── Multi-Track Timeline Engine ──
window.timelineState = {
  tracks: [], // { id, name, volume, mute, solo, clips: [] }
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
  
  // Initialize tracks if needed
  if(timelineState.tracks.length === 0 && fileQueue.length > 0) {
    for(let i=0; i<fileQueue.length; i++) {
      const dur = await getAudioDuration(fileQueue[i]);
      timelineState.tracks.push({
        id: 'trk_' + i,
        name: fileQueue[i].name,
        volume: 1, mute: false, solo: false,
        clips: [{
           id: 'clip_' + i + '_' + Date.now(),
           fileIdx: i,
           startOffset: (currentTool === 'merge' ? (i * dur) : 0),
           duration: dur,
           fileStart: 0 // offset inside the raw file
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
      <div style="font-size:0.8rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${track.name}</div>
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
             track.clips.push(newClip);
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
  
  const btn = document.getElementById('preview-mix-btn');
  if(window.isTimelinePlaying) {
    // stop
    window.timelineSources.forEach(s => { try{ s.source.stop(); }catch(e){} });
    window.timelineSources = [];
    clearInterval(window.timelineInterval);
    btn.innerHTML = '<i class="ph-fill ph-play"></i> Preview Mix';
    window.isTimelinePlaying = false;
  } else {
    // play
    btn.innerHTML = '<i class="ph-fill ph-stop"></i> Stop';
    window.isTimelinePlaying = true;
    
    // Check solo
    const anySolo = timelineState.tracks.some(t => t.solo);
    
    // Schedule all clips
    const t0 = audioCtx.currentTime;
    
    for (const track of timelineState.tracks) {
      if(track.mute) continue;
      if(anySolo && !track.solo) continue;
      
      for (const clip of track.clips) {
         const file = fileQueue[clip.fileIdx];
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
         
         // Non-destructive clip offset logic:
         // start at `t0 + clip.startOffset`
         // play the chunk of buffer starting at `clip.fileStart`
         // for duration `clip.duration`
         source.start(t0 + clip.startOffset, clip.fileStart, clip.duration);
         window.timelineSources.push({source, gain});
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

"""

with open(app_js, "w") as f:
    f.write(pre + advanced_timeline + "\n" + post)
print("Updated timeline architecture!")
