import re

app_js = "./web/static/js/app.js"
with open(app_js, "r") as f:
    code = f.read()

# 1. Replace getAudioDuration with loadAudioBuffer
code = code.replace("async function getAudioDuration(file) {", "async function loadAudioBuffer(file) {\n  if(file.audioBuffer) return file.audioBuffer;")
code = code.replace("resolve(buffer.duration);", "file.audioBuffer = buffer; resolve(buffer);")
code = code.replace("const dur = await getAudioDuration(fileQueue[i]);", "const buffer = await loadAudioBuffer(fileQueue[i]); const dur = buffer ? buffer.duration : 0;")

# 2. Add drawWaveform logic and inject into clip rendering
draw_func = """
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
"""

code = code.replace("window.renderTimeline = async function() {", draw_func + "\nwindow.renderTimeline = async function() {")

clip_render_old = """      clipEl.title = "Drag to move. Alt+Click to Razor (slice) at mouse.";"""
clip_render_new = """      clipEl.title = "Drag to move. Alt+Click to Razor (slice) at mouse.";
      
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
"""
code = code.replace(clip_render_old, clip_render_new)

# 3. Stop playback on delete/add/slice
stop_playback_logic = """
function ensurePlaybackStopped() {
  if (window.isTimelinePlaying) toggleMasterPlay();
}
"""
code = code.replace("window.playSingleTrack = function(trkIdx) {", stop_playback_logic + "\nwindow.playSingleTrack = function(trkIdx) {")
code = code.replace("timelineState.tracks.splice(trkIdx, 1);", "ensurePlaybackStopped(); timelineState.tracks.splice(trkIdx, 1);")

code = code.replace("track.clips.push(newClip);", "ensurePlaybackStopped(); track.clips.push(newClip);")


# 4. Use cached buffer in toggleMasterPlay instead of reading file again
play_old = """         const file = fileQueue[clip.fileIdx];
         const buffer = await new Promise(r => {
           const reader = new FileReader();
           reader.onload = async (e) => r(await audioCtx.decodeAudioData(e.target.result));
           reader.readAsArrayBuffer(file);
         });"""
play_new = """         const buffer = fileQueue[clip.fileIdx].audioBuffer;
         if(!buffer) continue;"""
code = code.replace(play_old, play_new)

with open(app_js, "w") as f:
    f.write(code)

print("Waveforms injected")
