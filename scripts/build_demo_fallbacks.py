#!/usr/bin/env python3
"""Render a short H.264 backup video from the verified replay JSON files."""
import hashlib, json, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent.parent
BUNDLE=ROOT/"results/defense_bundle/v1"
FRAMES=BUNDLE/".video_frames"
FALLBACKS=BUNDLE/"fallbacks"

def font(size,bold=False):
    candidates=["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf","/System/Library/Fonts/Helvetica.ttc"]
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def transform(bounds,w,h,pad=45):
    minx,miny,maxx,maxy=bounds;s=min((w-2*pad)/(maxx-minx),(h-2*pad)/(maxy-miny))
    return lambda x,y:(pad+(x-minx)*s,h-pad-(y-miny)*s)

def panel(replay,network,t,w=900,h=760):
    frame=min(replay["frames"],key=lambda f:abs(f["t"]-t));im=Image.new("RGB",(w,h),"#e8e5dc");d=ImageDraw.Draw(im);T=transform(network["bounds"],w,h)
    for edge in network["edges"]:
        pts=[T(*p) for p in edge["shape"]];d.line(pts,fill="#58646d",width=34,joint="curve");d.line(pts,fill="#d9d5c9",width=2)
    colors={"motorcycle":"#e76f51","car":"#2a9d8f","truck":"#e9c46a","bus":"#7a6fa6"}
    for _,x,y,angle,kind in frame["vehicles"]:
        px,py=T(x,y);r=3 if kind=="motorcycle" else 5;d.ellipse((px-r,py-r,px+r,py+r),fill=colors.get(kind,"#333"))
    phase=["NW-SE green","clearance","NE-SW green","clearance","turn movements green","clearance"][frame["p"]]
    d.text((24,20),phase,font=font(24,True),fill="#17324d");d.ellipse((w-60,20,w-25,55),fill="#e9c46a" if frame["p"]%2 else "#2a9d8f",outline="#17324d",width=3)
    d.rectangle((0,h-92,w,h),fill="#ffffff");labels=[f'Queue {int(frame["q"])} veh',f'Pending {frame["pending"]}',f'Arrived {frame["arrived"]}',f'Episode {replay["metrics"]["queue_integral_vehicle_hours"]:.1f} veh-h']
    for i,label in enumerate(labels): d.text((25+i*w/4,h-62),label,font=font(20,True),fill="#17324d")
    return im

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    FRAMES.mkdir(parents=True,exist_ok=True);FALLBACKS.mkdir(exist_ok=True)
    network=json.loads((BUNDLE/"network.json").read_text());left=json.loads((BUNDLE/"replays/test_pm_peak_demand103__published_fixed.json").read_text());right=json.loads((BUNDLE/"replays/test_pm_peak_demand103__dueling_n3.json").read_text())
    for i,t in enumerate(range(1800,2101,10)):
        out=Image.new("RGB",(1920,1080),"#f5f1e8");d=ImageDraw.Draw(out);d.rectangle((0,0,1920,110),fill="#17324d");d.text((45,26),"Da Nang PM peak: synchronized SUMO replay",font=font(38,True),fill="white");d.text((1500,38),f'{t//60:02d}:{t%60:02d}',font=font(32,True),fill="#e9c46a")
        out.paste(panel(left,network,t),(40,160));out.paste(panel(right,network,t),(980,160));d.text((310,122),"Published fixed time",font=font(27,True),fill="#17324d");d.text((1270,122),"Dueling DDQN",font=font(27,True),fill="#17324d");d.text((330,955),"Representative case. Aggregate PM result: DDQN 34.5% lower queue integral.",font=font(27,True),fill="#17324d")
        out.save(FRAMES/f"frame-{i:03d}.png")
    subprocess.run(["ffmpeg","-y","-framerate","2","-i",str(FRAMES/"frame-%03d.png"),"-c:v","libx264","-pix_fmt","yuv420p",str(FALLBACKS/"demo-walkthrough.mp4")],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    shutil.copy2(ROOT/"presentation/rendered/thesis_defense_danang.pdf",FALLBACKS/"result-summary.pdf")
    manifest=json.loads((BUNDLE/"manifest.json").read_text());manifest["fallbacks"]=[{"kind":"mp4","path":"fallbacks/demo-walkthrough.mp4","sha256":sha(FALLBACKS/"demo-walkthrough.mp4")},{"kind":"pdf","path":"fallbacks/result-summary.pdf","sha256":sha(FALLBACKS/"result-summary.pdf")},{"kind":"screenshot","path":"fallbacks/pm-peak.png","sha256":sha(FALLBACKS/"pm-peak.png")}];(BUNDLE/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(FALLBACKS)
if __name__=="__main__":main()
