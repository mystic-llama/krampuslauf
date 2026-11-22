"""Generate an offline, nonfunctional design preview from the actual UI layout."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui_layout import LAYOUTS, NAVIGATION, VERSION
from shard_policy import supported_shards
from ui_assets import artwork_bounds, artwork_path
from PIL import Image
from ui_theme import DARK, LIGHT


def literal(name):
    for n in ast.parse((ROOT / 'cycler_engine.py').read_text(encoding='utf8')).body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
            return ast.literal_eval(n.value)


import appearance

data = dict(style_groups=list(appearance.STYLE_LABELS.items()), layouts=LAYOUTS, navigation=NAVIGATION, version=VERSION,
            shards=supported_shards(literal('INITIAL_ORDER')), dark=DARK, light=LIGHT)
template = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Krampuslauf · Layout preview</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:32px;background:#101114;color:#eef0f3;font:14px Arial,sans-serif}
.intro{width:720px;margin:0 auto 20px;line-height:1.5}.intro strong{font-size:18px}.intro p{color:#aeb4bf;margin:6px 0}
.tools{display:flex;align-items:center;gap:12px;margin-top:12px}.tools button,.tools label{background:#2b2f36;color:#e9edf4;border:1px solid #414853;border-radius:6px;padding:8px 12px;font:13px Arial;cursor:pointer}
.tools input{display:none}.window{position:relative;width:720px;height:890px;margin:auto;border-radius:10px;background:var(--bg);box-shadow:0 24px 70px #0007;border:1px solid #45474b;overflow:hidden}
.titlebar{height:30px;display:flex;align-items:center;padding:0 10px;color:var(--muted);font-size:12px;background:var(--card)}#version{margin-left:4px}.caption-buttons{margin-left:auto;letter-spacing:20px;color:var(--ink)}
.client{position:absolute;left:7px;top:30px;width:704px;height:851px;color:var(--ink);font-family:'Segoe UI',Arial,sans-serif}
.brand{position:absolute;left:14px;right:14px;top:4px;height:144px;display:flex;align-items:center;justify-content:center;gap:15px}.brand b{display:block;font-size:22.667px;line-height:30px}.brand>img{width:74px;height:74px;object-fit:contain}.brand .title-art{position:relative;width:656px;height:144px;overflow:hidden}.title-art img{position:absolute;__TITLE_STYLE__;max-width:none}.artwork{object-fit:contain}
.main-nav{position:absolute;left:14px;top:152px;display:flex;gap:3px;height:36px;width:676px}.nav-btn{flex:1;min-width:0;height:32px;margin-top:1px;border:0;padding:0 4px;background:var(--bg);color:var(--ink);font:12.667px 'Segoe UI',Arial;cursor:pointer;border-radius:5px 5px 0 0;white-space:nowrap}.nav-btn.active{background:var(--panel);color:var(--accent);font-weight:700}.nav-btn:hover{background:var(--card)}
.sub-nav{position:absolute;left:14px;top:188px;height:36px;width:676px;display:flex;gap:3px;background:var(--bg)}.page{position:absolute;left:14px;top:224px;width:676px;height:613px;background:var(--panel)}.page.single{top:118px;height:559px}
.control{position:absolute}.text{font-size:14px;line-height:1.25;white-space:pre-wrap;overflow:hidden}.text.heading{font-size:17.333px;font-weight:700;color:var(--accent)}.text.muted{font-size:13.333px;color:var(--muted)}.text.note,.text.warning{font-size:12.667px;font-weight:700;color:var(--note)}.text.warning{color:var(--warning)}.text.next{display:flex;align-items:center;background:#1c2a19;color:#b7ff49;font-size:13.333px;font-weight:700;line-height:16px;padding:0 4px 0 8px}
.action{font:700 13.333px 'Segoe UI',Arial;color:var(--ink);background:var(--card);border:0;border-radius:6px;padding:0 8px;cursor:pointer;white-space:nowrap}.action.accent{background:#2867a4;color:white}.action.start{background:#21754d;color:white}.action:hover{filter:brightness(1.13)}
input,select,textarea,.log,.list{font:14px 'Segoe UI',Arial;color:var(--ink);background:var(--card);border:1px solid #6c6d70;border-radius:2px;padding:3px 5px}select{padding:2px 5px}textarea,.log{font:13.333px Consolas,'DejaVu Sans Mono',monospace;line-height:1.3;resize:none;overflow:auto;white-space:pre-wrap;word-break:break-word}.check{display:flex;align-items:center;gap:7px;font-size:14px;line-height:18px}.check input{accent-color:#3b8bd0;margin:0;width:14px;height:14px}.rule{background:var(--card)}.list{padding:5px;overflow:auto}.list div{line-height:20px}.note-bar{margin:16px auto 0;width:720px;color:#929caa;min-height:40px;font-size:13px;line-height:1.5}
</style>
<div class="intro"><strong>Krampuslauf · 720 × 890 layout</strong><p>Interactive layout preview from the application’s layout definitions. Native Windows rendering still needs verification.</p><div class="tools"><button id="themeToggle">Switch to light</button><span>Navigation works. Game actions are disabled.</span></div></div>
<div class="window" id="window"><div class="titlebar">Krampuslauf <span id="version"></span><span class="caption-buttons">− □ ×</span></div><div class="client"><div class="brand" id="brand"><div class="title-art"><img src="assets/title_banner.png" alt="Krampuslauf"></div></div><nav class="main-nav" id="mainNav" aria-label="Main tabs"></nav><nav class="sub-nav" id="subNav" aria-label="Subtabs"></nav><main class="page" id="page"></main></div></div><div class="note-bar" id="message">Choose a tab to explore the layout. Sample status values are illustrative.</div>
<script>
const DATA=__DATA__;
let currentPage='appearance',dark=true;
let currentGroup=DATA.navigation.findIndex(g=>g[1].some(p=>p[1]===currentPage));
const samples={game_pick:'Select the official Classic Client…',cycle_status_label:'Cycle: 2c7e8ca3',screen_status:'Game area: 640×480 at (8, 31).\nDisplay scaling: 100% of the 640×480 menu layout.\nRecognized screen: servers',map_status_label:'27 shards scanned — verified',seed_name_hint:'Format: Llama CAT b\nMax 16 characters; prefix 1–10 letters.',name_verified_label:'Typing: confirmed',isolation_status_label:'Active: all character links isolated\n30 profiles preserved · 24 links temporarily removed',status:'Ready — activity is saved locally.',test_status_label:'Saved successful tests: 8/10',health_status:'Version: '+DATA.version+'\nSetup checklist: 5/5 confirmed\nClassic Client: Selected for this launch\nProfile isolation: Active\nScreen recognition: built-in 640×480 menu layout (auto-scaled)\nShard map: 27 shards scanned — verified\nSeeder history: Loaded / saved\nName typing: Confirmed\nTheme: Dark'};
function palette(){let p=dark?DATA.dark:DATA.light;for(let k in p)document.getElementById('window').style.setProperty('--'+k,'rgb('+p[k].join(',')+')');document.getElementById('themeToggle').textContent=dark?'Switch to light':'Switch to dark'}
function navButton(title,active,fn){let b=document.createElement('button');b.className='nav-btn'+(active?' active':'');b.textContent=title;b.onclick=fn;return b}
function selectPage(key){currentPage=key;currentGroup=DATA.navigation.findIndex(g=>g[1].some(p=>p[1]===key));render()}
window.selectPage=selectPage;
function updateAppearancePalette(){
 const page=document.getElementById('page'),pick=page.querySelector('[data-ref="app_palette_pick"]');
 if(!pick)return;
 const race=page.dataset.race||'human',sex=page.dataset.sex||'male',part=pick.value;
 const available=part!=='facial'||(race!=='elf'&&sex==='male');
 const ref=part==='skin'?'skin_palettes.'+race:'color_palettes.'+race+'_'+part;
 for(const image of page.querySelectorAll('[data-ref^="skin_palettes."],[data-ref^="color_palettes."]'))
   image.style.display=available&&image.dataset.ref===ref?'':'none';
 const status=page.querySelector('[data-ref="skin_status"]');
 status.textContent=!available?(race==='elf'?'Elves have no facial hair.':'No facial hair or horns for this sex.'):
   part==='skin'?'No shade selected: random':'No colour selected: game default';
}
function render(){let main=document.getElementById('mainNav'),sub=document.getElementById('subNav'),page=document.getElementById('page');main.replaceChildren();sub.replaceChildren();page.replaceChildren();delete page.dataset.race;delete page.dataset.sex;
 DATA.navigation.forEach((g,i)=>main.append(navButton(g[0],i===currentGroup,()=>selectPage(g[1][0][1]))));
 const children=DATA.navigation[currentGroup][1];sub.style.display=children.length>1?'flex':'none';page.classList.toggle('single',children.length===1);page.dataset.page=currentPage;
 children.forEach(c=>sub.append(navButton(c[0],c[1]===currentPage,()=>selectPage(c[1]))));
 for(const s of DATA.layouts[currentPage]){let e;let value=samples[s.ref]??s.default??'';
  if(s.source==='shards')value=DATA.shards.join('\n');if(s.source==='slot_rules')value='Origin: 1,2,3';
  if(s.kind==='text'){e=document.createElement('div');e.className='text '+s.role;e.textContent=samples[s.ref]??s.text}
  else if(s.kind==='image'){e=document.createElement('img');e.className='artwork';e.src='assets/'+s.asset;e.alt=s.text;if(s.action){e.style.cursor='pointer';e.title=s.text;e.onclick=()=>document.getElementById('message').textContent='Preview only: “'+s.text+'” opens in the Windows application.'}}
  else if(s.kind==='button'){e=document.createElement('button');e.className='action '+(s.tone||'');e.textContent=s.text;e.onclick=()=>{if(s.action.startsWith('page:'))selectPage(s.action.slice(5));else document.getElementById('message').textContent='Preview only: “'+s.text+'” is available in the Windows application.'}}
  else if(s.kind==='check'||s.kind==='radio'){e=document.createElement('label');e.className='check';let input=document.createElement('input');input.type=s.kind==='radio'?'radio':'checkbox';if(s.kind==='radio')input.name='account_slot';input.checked=s.kind==='radio'?s.ref.endsWith('.main'):s.ref.startsWith('setup_checks.')||s.ref==='sort_confirm'||s.ref==='create_missing_checkbox';let caption=document.createElement('span');caption.textContent=s.kind==='radio'?(s.ref.endsWith('.main')?'Main Account':'Account '+s.ref.split('.account')[1]):s.text;caption.style.whiteSpace='pre-line';e.append(input,caption);if(s.ref.startsWith('app_checks.race_')||s.ref.startsWith('app_checks.sex_'))input.onchange=()=>{let group=s.ref.includes('.race_')?'race':'sex';if(input.checked){page.dataset[group]=s.ref.split(group+'_')[1];if(page.querySelector('[data-ref="app_mode"]').value==='fixed')for(let box of page.querySelectorAll('[data-ref^="app_checks.'+group+'_"] input'))if(box!==input)box.checked=false}updateAppearancePalette()}}
  else if(s.kind==='choice'){e=document.createElement('select');let choices=s.items||[];if(s.source==='style_groups')choices=DATA.style_groups.map(([v,t])=>[t,v]);if(!choices.length)choices=s.ref==='game_pick'?[[value,'']]:DATA.shards.map(t=>[t,t]);for(let [t,v]of choices){let o=document.createElement('option');o.textContent=t;o.value=v;e.append(o)}if(s.items)e.value=s.default;e.onchange=()=>{if(s.ref==='app_palette_pick')updateAppearancePalette();if(s.ref==='seed_mode_pick'){document.querySelector('[data-ref="seed_style_pick"]').disabled=e.value!=='fantasy';document.querySelector('[data-ref="seed_prefix_field"]').disabled=e.value==='fantasy';document.querySelector('[data-ref="seed_name_hint"]').textContent=e.value==='fantasy'?samples.seed_name_hint:'Prefix + shard + slot.\n1-10 prefix letters.\nMax 16 characters.'}}}
  else if(s.kind==='textarea'){e=document.createElement('textarea');e.value=value}
  else if(s.kind==='log'){e=document.createElement('div');e.className='log';e.textContent='[20:14:04] Selected official Classic Client window.\n[20:14:12] Shard map: 27 shards verified.\n[20:14:16] Settings saved locally.\n\nSample history for layout preview only.'}
  else if(s.kind==='checklist'){e=document.createElement('div');e.className='list';for(let [i,title] of (s.ref==='shard_checks'?DATA.shards:['NONE','Short','Long','Pony Tail','Mohawk','Pageboy']).entries()){let d=document.createElement('label');d.className='check';let c=document.createElement('input');c.type='checkbox';c.checked=s.ref==='shard_checks'||i===1;let t=document.createElement('span');t.textContent=title;d.append(c,t);e.append(d)}}
  else if(s.kind==='palette'){e=document.createElement('img');e.className='artwork';e.src='assets/'+s.asset;e.alt=s.text;e.style.imageRendering='pixelated';if(s.stack==='skin' && s.ref!=='skin_palettes.human')e.style.display='none'}
  else if(s.kind==='list'){e=document.createElement('div');e.className='list';for(let title of ['Legends','Atlantic','Lake Superior','Great Lakes']){let d=document.createElement('div');d.textContent=title;e.append(d)}}
  else if(s.kind==='rule'){e=document.createElement('div');e.className='rule'}
  else {e=document.createElement('input');e.type=s.kind==='number'?'number':'text';e.value=value;if(s.low!==undefined){e.min=s.low;e.max=s.high}}
  e.classList.add('control');e.dataset.ref=s.ref||'';e.style.cssText+=`left:${s.x}px;top:${s.y}px;width:${s.w}px;height:${s.h}px;`;if(s.ref==='seed_prefix_field')e.disabled=true;page.append(e);
 }
 updateAppearancePalette();
}
document.getElementById('themeToggle').onclick=()=>{dark=!dark;palette()};
document.getElementById('version').textContent=' '+DATA.version;palette();render();
</script></html>'''

bounds = artwork_bounds('title_banner.png')
with Image.open(artwork_path('title_banner.png')) as image:
    x, y, w, h = bounds
    title_style = 'width:{}%;height:{}%;left:{}%;top:{}%'.format(
        image.width / w * 100, image.height / h * 100, -x / w * 100, -y / h * 100)
template = template.replace('__TITLE_STYLE__', title_style)
target = ROOT / 'Krampuslauf_Layout_Preview.html'
target.write_text(template.replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/')), encoding='utf8')
print(target)
