"""Local video preparation and rendering. Requires ffmpeg and ffprobe on PATH.

No social credentials or uploads. Source media stays outside the repository.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

EXTENSIONS={'.mp4','.mov','.mkv','.webm','.m4v'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def binary_path(binary):
    location=os.environ.get(binary.upper()+'_BINARY') or shutil.which(binary)
    if not location and binary=='ffmpeg':
        try:
            import imageio_ffmpeg
            location=imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
    return location


def execute(binary,arguments,timeout=180):
    location=binary_path(binary)
    if not location: raise RuntimeError('Install '+binary+' before using video preparation/rendering')
    result=subprocess.run([location]+arguments,capture_output=True,text=True,timeout=timeout,check=False)
    if result.returncode: raise RuntimeError(binary+' failed: '+result.stderr[-1500:])
    return result.stdout


def probe(path):
    p=Path(path).resolve(strict=True)
    if not binary_path('ffprobe'):
        ff=binary_path('ffmpeg')
        if not ff: raise RuntimeError('Install FFmpeg, or the optional imageio-ffmpeg Python package')
        result=subprocess.run([ff,'-hide_banner','-nostdin','-i',str(p)],capture_output=True,text=True,timeout=30)
        duration=re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)',result.stderr)
        video=next((line for line in result.stderr.splitlines() if 'Video:' in line), '')
        size=re.search(r'\b(\d{2,5})x(\d{2,5})\b',video)
        if not duration or not size: raise ValueError('Cannot determine video duration/dimensions; install ffprobe for this format')
        seconds=int(duration[1])*3600+int(duration[2])*60+float(duration[3])
        if seconds<=0: raise ValueError('Video duration must be positive')
        return {'duration_seconds':seconds,'width':int(size[1]),'height':int(size[2]),'has_audio':'Audio:' in result.stderr}
    data=json.loads(execute('ffprobe',['-v','error','-show_format','-show_streams','-of','json',str(p)]))
    duration=float(data.get('format',{}).get('duration',0))
    video=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),None)
    if not video or not math.isfinite(duration) or duration<=0: raise ValueError('Need a video with a known positive duration')
    return {'duration_seconds':duration,'width':video.get('width'),'height':video.get('height'),
            'has_audio':any(s.get('codec_type')=='audio' for s in data.get('streams',[]))}


def prepare(video,job,library=None,transcribe=False):
    source=Path(video).resolve(strict=True)
    dest=Path(job).resolve()
    if dest.exists() and any(dest.iterdir()): raise ValueError('Choose an empty job directory; existing work is never overwritten')
    dest.mkdir(parents=True,exist_ok=True)
    info=probe(source)
    paths=[source]
    if library:
        root=Path(library).resolve(strict=True)
        # Explicitly scoped directory; no search of the whole computer.
        for p in sorted(root.rglob('*')):
            if p.is_symlink() or not p.is_file() or p.suffix.lower() not in EXTENSIONS: continue
            resolved=p.resolve()
            if root not in resolved.parents: continue
            if resolved not in paths: paths.append(resolved)
            if len(paths)>=25: break
    assets=[]
    for i,p in enumerate(paths):
        try:
            meta=info if i==0 else probe(p)
            assets.append({'id':'asset-'+str(i),'path':str(p),'sha256':sha(p),**meta,
                           'filename_hint':p.stem,'relevance':'unassessed; filename is not semantic evidence'})
        except (ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
            assets.append({'id':'asset-'+str(i),'path':str(p),'error':str(exc)})
    frames=[]
    for i in range(6):
        second=min(info['duration_seconds']-.05,info['duration_seconds']*(i+.5)/6)
        second=max(0,second)
        filename='frame-%02d.jpg'%i
        execute('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-ss',str(second),'-i',str(source),
                          '-frames:v','1','-vf','scale=768:-2','-q:v','3',str(dest/filename)])
        frames.append({'second':round(second,3),'file':filename})
    segments=[]
    status='missing'
    if info['has_audio']:
        audio=dest/'source-audio.wav'
        execute('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-i',str(source),'-vn','-ac','1','-ar','16000',str(audio)])
        if transcribe:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError('Optional transcription needs faster-whisper. Install it, or supply a timed transcript. Prepared frames/audio remain in the job folder.') from exc
            model=WhisperModel('base',device='cpu',compute_type='int8')
            generated,_=model.transcribe(str(audio),vad_filter=True)
            segments=[{'id':'s'+str(i+1),'start':s.start,'end':min(s.end,info['duration_seconds']),'text':s.text.strip()} for i,s in enumerate(generated)]
            status='machine_generated_unreviewed'
    manifest={'duration_seconds':info['duration_seconds'],'rights':'unknown','privacy_review':'pending',
              'transcript_status':status,'segments':segments,'frames':frames,
              'context_note':'Six sampled frames are not complete video coverage. Re-check candidate cut boundaries before approving.'}
    (dest/'clip-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (dest/'assets.json').write_text(json.dumps({'assets':assets,'library_limit':25,'selection':'primary video first, then alphabetical library paths'},indent=2)+'\n')
    (dest/'NEXT.md').write_text('Review the transcript and rights. Use the social-editor with this folder as its workspace. Draft an edit plan with asset IDs and timings. If narration is needed, save the script and record narration.wav. Render a preview, review it, and revise the plan. Nothing is posted automatically.\n')
    return {'job':str(dest),'assets':len(assets),'frames':len(frames),'transcript_status':status,'posted':False}


def validate_edit(plan,assets):
    indexed={a['id']:a for a in assets if 'error' not in a}
    if plan.get('canvas') not in ('portrait','landscape','square','feed'): raise ValueError('canvas must be portrait, landscape, square or feed')
    clips=plan.get('clips',[])
    if not isinstance(clips,list) or not 1<=len(clips)<=20: raise ValueError('Use 1–20 clips')
    total=0
    for clip in clips:
        if clip.get('asset_id') not in indexed: raise ValueError('Unknown asset ID')
        start,end=clip.get('start'),clip.get('end')
        if type(start) not in (int,float) or type(end) not in (int,float): raise ValueError('Timings must be numbers')
        if not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end<=indexed[clip['asset_id']]['duration_seconds']:
            raise ValueError('Clip is outside source duration')
        if type(clip.get('keep_audio',True)) is not bool: raise ValueError('keep_audio must be boolean')
        if clip.get('fit','contain') not in ('contain','cover'): raise ValueError('fit must be contain or cover')
        for key in ('focus_x','focus_y'):
            value=clip.get(key,.5)
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1: raise ValueError(key+' must be between 0 and 1')
        if clip.get('grade','neutral') not in ('neutral','gym'): raise ValueError('Unknown grade')
        total+=end-start
    if total>180: raise ValueError('Prototype preview limit is 180 seconds')
    return {'duration_seconds':total,'clips':len(clips),'asset_ids':sorted({c['asset_id'] for c in clips})}


def render(job,planfile,output,narration=None):
    root=Path(job).resolve(strict=True)
    assets=json.loads((root/'assets.json').read_text())['assets']
    plan=json.loads(Path(planfile).read_text())
    validation=validate_edit(plan,assets)
    indexed={a['id']:a for a in assets}
    destination=Path(output).resolve()
    if destination.exists(): raise ValueError('Output already exists; choose a new version filename')
    destination.parent.mkdir(parents=True,exist_ok=True)
    narration_path=Path(narration).resolve(strict=True) if narration else None
    for identity in validation['asset_ids']:
        item=indexed[identity]
        if sha(item['path'])!=item['sha256']: raise ValueError('Source changed since indexing; prepare a new job')
    width,height={'portrait':(720,1280),'landscape':(1280,720),'square':(720,720),'feed':(864,1080)}[plan['canvas']]
    with tempfile.TemporaryDirectory(prefix='agent-edit-') as temp:
        temp=Path(temp); files=[]
        for i,clip in enumerate(plan['clips']):
            item=indexed[clip['asset_id']]; duration=clip['end']-clip['start']; piece=temp/('%03d.mp4'%i)
            if clip.get('fit','contain')=='cover':
                filter_video='scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d:(iw-ow)*%s:(ih-oh)*%s'%(width,height,width,height,clip.get('focus_x',.5),clip.get('focus_y',.5))
            else:
                filter_video='scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2'%(width,height,width,height)
            filter_video+=',setsar=1,fps=30'
            if clip.get('grade')=='gym': filter_video+=',eq=contrast=1.10:brightness=-0.015:saturation=0.92,unsharp=5:5:0.4:5:5:0'
            args=['-hide_banner','-loglevel','error','-nostdin','-ss',str(clip['start']),'-i',item['path']]
            original_audio=item['has_audio'] and clip.get('keep_audio',True) and not narration_path
            if not original_audio: args+=['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000']
            args+=['-map','0:v:0','-map','0:a:0' if original_audio else '1:a:0','-t',str(duration),'-vf',filter_video,
                   '-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2',str(piece)]
            execute('ffmpeg',args,timeout=300); files.append(piece)
        listing=temp/'concat.txt'
        listing.write_text(''.join("file '%s'\n"%p.as_posix() for p in files))
        joined=temp/'joined.mp4'
        execute('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(joined)],timeout=300)
        if narration_path:
            execute('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-i',str(joined),'-i',str(narration_path),'-map','0:v:0','-map','1:a:0',
                              '-c:v','copy','-af','apad','-t',str(validation['duration_seconds']),'-c:a','aac','-movflags','+faststart',str(destination)],timeout=300)
        else:
            shutil.copyfile(joined,destination)
    receipt={'preview':str(destination),'sha256':sha(destination),'plan_sha256':sha(planfile),**validation,
             'status':'preview_requires_review','posted':False,'narration':bool(narration_path)}
    destination.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    p=argparse.ArgumentParser(description='Prepare local video evidence or render an explicit edit plan. No publishing.')
    sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare'); a.add_argument('video'); a.add_argument('--job',required=True); a.add_argument('--library'); a.add_argument('--transcribe',action='store_true')
    b=sub.add_parser('render'); b.add_argument('--job',required=True); b.add_argument('--plan',required=True); b.add_argument('--output',required=True); b.add_argument('--narration')
    args=p.parse_args()
    try:
        result=prepare(args.video,args.job,args.library,args.transcribe) if args.action=='prepare' else render(args.job,args.plan,args.output,args.narration)
        print(json.dumps(result,indent=2)); return 0
    except Exception as exc:
        p.exit(1,'Error: '+str(exc)+'\n')


if __name__=='__main__': raise SystemExit(main())
