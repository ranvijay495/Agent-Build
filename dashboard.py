"""Builds dashboard.html (dense sortable light table) from jobs.db and sends it to Telegram."""
import sqlite3, os, datetime, json
import notify

DB = os.environ.get("DB_PATH", "jobs.db")

def build():
    c = sqlite3.connect(DB)
    rows = c.execute("""SELECT posted_date,title,company,location,portal,score,cv_choice,status,url
                        FROM jobs ORDER BY posted_date DESC""").fetchall()
    data = [{"d": r[0] or "", "r": r[1], "c": r[2], "l": r[3] or "", "p": r[4] or "",
             "s": r[5] if r[5] is not None else "", "cv": (r[6] or "").replace("corpdev_ma", "M&A").replace("chief_of_staff", "CoS"),
             "st": r[7] or "new", "u": r[8] or "#"} for r in rows]
    now = datetime.datetime.now().strftime("%d %b %Y, %H:%M UTC")
    html = """<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><meta name='robots' content='noindex'>
<title>Job Pipeline</title><style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#1f2937;margin:0;padding:16px}
h1{font-size:18px;margin:0} .sub{color:#6b7280;font-size:13px;margin:2px 0 14px}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}
input,select{padding:7px 10px;border:1px solid #d1d5db;border-radius:7px;font-size:13px}
input{flex:1;min-width:170px}
.kpis{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:#6b7280;margin-bottom:10px}
.kpis b{color:#111827;font-weight:600}
.wrap{border:1px solid #e5e7eb;border-radius:9px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:760px}
th{cursor:pointer;text-align:left;padding:9px 10px;font-weight:600;color:#6b7280;border-bottom:1px solid #e5e7eb;white-space:nowrap;background:#f9fafb;position:sticky;top:0}
td{padding:7px 10px;border-bottom:1px solid #f3f4f6;vertical-align:top}
tr:nth-child(even){background:#fafafa}
.pill{background:#eef2ff;color:#4338ca;border-radius:5px;padding:1px 7px;font-size:12px;white-space:nowrap}
.st{border-radius:10px;padding:2px 9px;font-size:12px;white-space:nowrap}
.st.queued{background:#dcfce7;color:#15803d}.st.approved{background:#e0e7ff;color:#4338ca}
.st.applied{background:#dbeafe;color:#1d4ed8}.st.manual{background:#fef3c7;color:#b45309}
.st.skipped{background:#f3f4f6;color:#9ca3af}.st.new,.st.scored{background:#e0f2fe;color:#0369a1}
.st.interview{background:#ede9fe;color:#6d28d9}.st.rejected{background:#fee2e2;color:#b91c1c}
a{color:#2563eb;text-decoration:none;font-weight:600}
</style></head><body>
<h1>Job Pipeline</h1><div class='sub'>Last sweep: __NOW__ · __N__ roles · CV switches happen on the Telegram card</div>
<div class='bar'><input id='q' placeholder='Search role or company' oninput='draw()'/>
<select id='fp' onchange='draw()'><option value=''>All portals</option></select>
<select id='fs' onchange='draw()'><option value=''>All statuses</option></select>
<select id='fr' onchange='draw()'><option value=''>India + Gulf</option><option>India</option><option>Gulf</option></select></div>
<div class='kpis' id='kpis'></div>
<div class='wrap'><table><thead><tr id='hdr'></tr></thead><tbody id='tb'></tbody></table></div>
<script>
const DATA=__DATA__;
const COLS=[['d','Posted'],['r','Role'],['c','Company'],['l','Location'],['p','Portal'],['s','Score'],['cv','CV'],['st','Status']];
let sk='d',asc=false;
const GULF=['uae','united arab emirates','dubai','abu dhabi','saudi','riyadh','doha','qatar','kuwait','bahrain','oman'];
[...new Set(DATA.map(x=>x.p))].sort().forEach(p=>fp.add(new Option(p)));
[...new Set(DATA.map(x=>x.st))].sort().forEach(s=>fs.add(new Option(s)));
function srt(k){asc=(sk===k)?!asc:true;sk=k;draw();}
function draw(){
 hdr.innerHTML=COLS.map(([k,n])=>`<th onclick="srt('${k}')">${n}${sk===k?(asc?' \u2191':' \u2193'):''}</th>`).join('')+'<th></th>';
 const q=document.getElementById('q').value.toLowerCase(),p=fp.value,s=fs.value,r=fr.value;
 let rows=DATA.filter(x=>(!q||(x.r+x.c).toLowerCase().includes(q))&&(!p||x.p===p)&&(!s||x.st===s));
 if(r==='Gulf')rows=rows.filter(x=>GULF.some(g=>x.l.toLowerCase().includes(g)));
 if(r==='India')rows=rows.filter(x=>!GULF.some(g=>x.l.toLowerCase().includes(g)));
 rows.sort((a,b)=>{const A=a[sk],B=b[sk];return(A>B?1:A<B?-1:0)*(asc?1:-1);});
 tb.innerHTML=rows.map(x=>`<tr><td style='white-space:nowrap;color:#6b7280'>${x.d}</td>
 <td style='font-weight:600'>${x.r}</td><td>${x.c}</td><td style='color:#6b7280'>${x.l}</td>
 <td><span class='pill'>${x.p}</span></td><td style='font-weight:600'>${x.s}</td><td>${x.cv}</td>
 <td><span class='st ${x.st}'>${x.st}</span></td><td><a href='${x.u}' target='_blank'>Open</a></td></tr>`).join('');
 const cnt={};rows.forEach(x=>cnt[x.st]=(cnt[x.st]||0)+1);
 kpis.innerHTML=`<span><b>${rows.length}</b> shown</span>`+Object.entries(cnt).map(([k,v])=>`<span>${k}: <b>${v}</b></span>`).join('');
}
draw();
</script></body></html>"""
    html = html.replace("__NOW__", now).replace("__N__", str(len(data))).replace("__DATA__", json.dumps(data))
    with open("dashboard.html", "w") as f:
        f.write(html)
    print(f"Dashboard written: {len(data)} roles")
    notify.send_document("dashboard.html", caption="Your pipeline after today's sweep")

if __name__ == "__main__":
    build()
