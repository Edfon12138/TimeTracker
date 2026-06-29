"""Generate stats HTML page with live editing via built-in HTTP server."""
import os, json, sqlite3, webbrowser, tempfile, base64, threading, http.server, socket
from datetime import datetime, timedelta, date as dt_date
import time, storage, config as cfg, icon_extractor

_server = None; _port = None


def _icon_svg(letter: str, color: str, size: int = 20) -> str:
    r = max(2, round(size * 0.18)); fs = round(size * 0.55)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
           f'<rect width="{size}" height="{size}" rx="{r}" fill="{color}"/>'
           f'<text x="{size//2}" y="{size//2+fs*0.35}" text-anchor="middle" '
           f'fill="white" font-size="{fs}" font-weight="bold" '
           f'font-family="Segoe UI,sans-serif">{letter}</text></svg>')
    return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"

def _add_icons(items):
    for item in items:
        label = item.get("label") or item.get("process", "")
        letter = (os.path.splitext(label)[0] or "?")[0].upper()
        item["icon_uri"] = _icon_svg(letter, item.get("color", "#888"))
    return items

def _get_chart_data(vm, df, dt2, drill=None):
    conf = cfg.load_config()
    cm = {c: conf["categories"].get(c, {}).get("color", "#5A5A5A") for c in conf["categories"]}
    if vm == "category" and not drill:
        rows = storage.get_range_summary(df, dt2)
        return _add_icons([{"label": r["category"], "value": r["total_seconds"],
                "color": cm.get(r["category"], "#5A5A5A"), "hk": r["category"], "type": "category"} for r in rows])
    rows = storage.get_program_stats(df, dt2)
    return _add_icons([{"label": r["process"], "value": r["total_seconds"],
            "color": icon_extractor.get_icon_color(r["process"]), "hk": r["process"], "type": "program"} for r in rows])


def generate():
    today = dt_date.today().isoformat()
    ws = (dt_date.today() - timedelta(days=dt_date.today().weekday())).isoformat()
    ms = dt_date.today().replace(day=1).isoformat()

    dp = {
        "today": {"cat": _get_chart_data("category", today, today), "prog": _get_chart_data("program", today, today)},
        "week": {"cat": _get_chart_data("category", ws, today), "prog": _get_chart_data("program", ws, today)},
        "month": {"cat": _get_chart_data("category", ms, today), "prog": _get_chart_data("program", ms, today)},
        "timeline": _add_icons([dict(r) for r in storage.get_activity_timeline(today)]),
        "config": cfg.load_config(),
    }

    # ── Merge idle/video sessions into stats ──
    import idle_detector
    idle_sessions = idle_detector.get_idle_sessions()
    idle_cat_today = {"空闲": 0, "视频": 0}
    idle_timeline = []
    for s in idle_sessions:
        cat = s["category"]
        dur = s["duration"]
        idle_cat_today[cat] = idle_cat_today.get(cat, 0) + dur
        idle_timeline.append({
            "process": s["process"] or "(无)",
            "window_title": s["window_title"] or (f"[{cat}]" if cat == "视频" else "[无操作]"),
            "category": cat,
            "color": "#6B7280" if cat == "空闲" else "#8B5CF6",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["started_at"])),
            "duration": dur,
            "icon_uri": _icon_svg("空"[0] if cat == "空闲" else "视", "#6B7280" if cat == "空闲" else "#8B5CF6"),
        })

    # Merge into today's category stats
    for cat, secs in idle_cat_today.items():
        if secs > 0:
            dp["today"]["cat"].append({"label": cat, "value": secs, "color": "#6B7280" if cat == "空闲" else "#8B5CF6", "hk": cat, "type": "category"})

    # Merge into week/month (only today's data, since idle sessions are memory-only)
    for rn in ("week", "month"):
        for cat, secs in idle_cat_today.items():
            if secs > 0:
                existing = [x for x in dp[rn]["cat"] if x["label"] == cat]
                if existing:
                    existing[0]["value"] += secs
                else:
                    dp[rn]["cat"].append({"label": cat, "value": secs, "color": "#6B7280" if cat == "空闲" else "#8B5CF6", "hk": cat, "type": "category"})

    # Merge idle sessions into timeline (sorted by time)
    dp["timeline"].extend(idle_timeline)
    dp["timeline"].sort(key=lambda x: x.get("started_at", ""))

    conn = sqlite3.connect(storage._db_path()); conn.row_factory = sqlite3.Row
    for rn, f, t_ in [("today", today, today), ("week", ws, today), ("month", ms, today)]:
        rows = conn.execute(
            "SELECT process,category,SUM(duration) AS total_seconds FROM activity_log "
            "WHERE date BETWEEN ? AND ? GROUP BY process,category ORDER BY category,total_seconds DESC", (f, t_)).fetchall()
        g = {}
        for r in rows:
            d = dict(r); d["color"] = icon_extractor.get_icon_color(d["process"])
            g.setdefault(d["category"], []).append(d)
        for c_ in g: _add_icons(g[c_])
        dp[f"progs_by_cat_{rn}"] = g
    conn.close()

    global _server, _port

    class _H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_OPTIONS(self):
            self.send_response(200); self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Access-Control-Allow-Methods","POST,OPTIONS"); self.send_header("Access-Control-Allow-Headers","Content-Type")
            self.end_headers()
        def do_POST(self):
            if self.path=="/save-config":
                try:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
                    cfg.save_config(body); storage.save_rules_to_db(body.get("rules",[]))
                    resp = json.dumps({"ok":True,"config":cfg.load_config()})
                except Exception as e:
                    resp = json.dumps({"ok":False,"error":str(e)})
                self.send_response(200); self.send_header("Content-Type","application/json")
                self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                self.wfile.write(resp.encode())
        def do_GET(self):
            if self.path=="/":
                json_data = json.dumps(dp, ensure_ascii=False)
                html = HTML_TEMPLATE.replace("__EMBEDDED_DATA__", json_data)
                self.send_response(200); self.send_header("Content-Type","text/html;charset=utf-8")
                self.end_headers(); self.wfile.write(html.encode("utf-8"))
            else:
                self.send_response(404); self.end_headers()

    if _server is None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.bind(("127.0.0.1", 0)); _port = s.getsockname()[1]; s.close()
        _server = http.server.ThreadingHTTPServer(("127.0.0.1", _port), _H)
        t = threading.Thread(target=_server.serve_forever, daemon=True); t.start()
    webbrowser.open(f"http://127.0.0.1:{_port}/")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>时间统计</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#16181D;color:#EAE4D9;font-family:'Segoe UI','Microsoft YaHei',sans-serif;padding:30px 20px}
.panel{max-width:860px;margin:0 auto;background:#1E2027;border-radius:12px;border:1px solid #2E3039;overflow:hidden}
.tabs{display:flex;border-bottom:1px solid #2E3039;align-items:center}
.tab{padding:14px 20px;font-size:13px;font-weight:500;color:#9B958A;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .15s;user-select:none}
.tab:hover{color:#EAE4D9}
.tab.active{color:#D4956B;border-bottom-color:#D4956B}
.tab-spacer{flex:1}
.btn-gear{background:none;border:none;color:#9B958A;font-size:18px;cursor:pointer;padding:12px 14px;transition:color .15s}
.btn-gear:hover{color:#D4956B}
.content{padding:20px 24px 24px}
.toolbar{display:flex;align-items:center;gap:16px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #2E3039;flex-wrap:wrap}
.tg{display:flex;background:#24262E;border-radius:6px;overflow:hidden;border:1px solid #2E3039}
.tb{padding:5px 14px;font-size:12px;font-family:inherit;color:#9B958A;cursor:pointer;border:none;background:transparent;transition:all .1s}
.tb.active{background:#D4956B;color:#1A1C21;font-weight:600}
.tb:hover:not(.active){color:#EAE4D9}
.tl{font-size:11px;color:#5E5A54;text-transform:uppercase;letter-spacing:.06em;margin-right:4px}
.spacer{flex:1}
.main{display:flex;gap:24px;flex-wrap:wrap}
.chart-box{width:300px;height:280px;position:relative;flex-shrink:0}
.breakdown{flex:1;min-width:240px;display:flex;flex-direction:column;gap:4px}
.bi{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;background:#24262E;cursor:pointer;transition:all .12s}
.bi:hover{background:#2C2E36}
.bi.dimmed:not(.hl){opacity:.3;transition:opacity .2s}
.bi.hl{box-shadow:inset 0 0 0 1px rgba(212,149,107,.5);background:#2A2E35}
.pgm-icon{width:22px;height:22px;border-radius:4px;flex-shrink:0;display:inline-block;vertical-align:middle}
.info{flex:1;min-width:0}
.name{font-size:13px;color:#EAE4D9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-w{width:60px;height:3px;background:#2E3039;border-radius:2px;overflow:hidden;flex-shrink:0}
.bar-f{height:100%;border-radius:2px;transition:width .2s}
.tm{font-family:Consolas,'Cascadia Code',monospace;font-size:14px;font-weight:500;color:#EAE4D9;width:56px;text-align:right;flex-shrink:0}
.pct{font-family:Consolas,monospace;font-size:11px;color:#5E5A54;width:32px;text-align:right;flex-shrink:0}
.sl{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#5E5A54;margin:16px 0 10px;display:flex;align-items:center;gap:8px}
.sl::after{content:'';flex:1;height:1px;background:#2E3039}
.tr{display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:4px;font-size:12px;transition:background .12s}
.tr:hover{background:#24262E}
.tt{font-family:Consolas,monospace;font-size:11px;color:#5E5A54;width:48px;flex-shrink:0}
.ttl{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.td{font-family:Consolas,monospace;font-size:12px;font-weight:500;color:#EAE4D9;width:52px;text-align:right;flex-shrink:0}
.tc{font-size:10px;padding:2px 8px;border-radius:3px;font-weight:500;width:42px;text-align:center;flex-shrink:0}
.footer{display:flex;gap:10px;justify-content:flex-end;margin-top:20px;padding-top:16px;border-top:1px solid #2E3039}
.btn{padding:7px 16px;border-radius:6px;font-size:12px;font-family:inherit;cursor:pointer;border:1px solid #2E3039;background:#24262E;color:#9B958A;transition:all .12s}
.btn:hover{color:#EAE4D9;border-color:#4A4D56}
.btn-p{background:#D4956B;color:#1A1C21;border-color:#D4956B;font-weight:600}
.btn-p:hover{background:#E8B48A}
.btn-r{background:#5C2D2D;color:#E85D75;border-color:#5C2D2D}
.btn-r:hover{background:#6D3A3A}
.bread{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#D4956B;cursor:pointer}
.bread:hover{color:#E8B48A}

/* Settings modal */
.mo{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center}
.mo.show{display:flex}
.mo-box{background:#1E2027;border:1px solid #2E3039;border-radius:12px;width:720px;max-height:85vh;overflow-y:auto;padding:24px}
.mo-box h2{font-size:16px;color:#EAE4D9;margin-bottom:12px}
.mo-box .tbl{width:100%;border-collapse:collapse;font-size:12px}
.mo-box .tbl th{background:#2E3039;color:#9B958A;padding:7px 8px;text-align:left;font-weight:500;position:sticky;top:0}
.mo-box .tbl td{padding:4px 8px;border-bottom:1px solid #2E3039}
.mo-box .tbl tr:hover td{background:#24262E}
.mo-box .tbl input,.mo-box .tbl select{background:#16181D;color:#EAE4D9;border:1px solid #2E3039;padding:4px 7px;border-radius:4px;font-size:12px;width:100%;font-family:inherit}
.mo-box .tbl select{width:auto}
.mo-box .tbl input:focus,.mo-box .tbl select:focus{outline:none;border-color:#D4956B}
</style>
</head>
<body>
<div class="panel" id="app">
  <div class="tabs" id="timeTabs">
    <div class="tab active" data-r="today">今日</div>
    <div class="tab" data-r="week">本周</div>
    <div class="tab" data-r="month">本月</div>
    <div class="tab-spacer"></div>
    <button class="btn-gear" id="gearBtn" title="设置">&#9881;</button>
  </div>
  <div class="content">
    <div class="toolbar">
      <span class="tl">视图</span>
      <div class="tg"><button class="tb active" data-v="cat">按分类</button><button class="tb" data-v="prog">按程序</button></div>
      <span class="tl">图表</span>
      <div class="tg"><button class="tb active" data-c="donut">饼图</button><button class="tb" data-c="bar">柱状图</button></div>
      <div class="spacer"></div>
      <div class="bread" id="bread" style="display:none"><span id="breadBack">&#8592; 返回全部</span></div>
    </div>
    <div class="main">
      <div class="chart-box"><canvas id="chartCanvas"></canvas></div>
      <div class="breakdown" id="breakdownList"></div>
    </div>
    <div class="sl">时间线</div>
    <div id="timeline"></div>
    <div class="footer">
      <button class="btn" id="exportBtn">导出 CSV</button>
    </div>
  </div>
</div>

<!-- Settings modal -->
<div class="mo" id="settingsModal">
  <div class="mo-box">
    <h2>分类规则设置</h2>
    <table class="tbl"><thead><tr><th style="width:28%">进程</th><th style="width:38%">标题匹配(正则)</th><th>分类</th><th style="width:40px"></th></tr></thead><tbody id="rulesBody"></tbody></table>
    <div style="margin-top:8px"><button class="btn" id="addRuleBtn">+ 添加规则</button></div>
    <p class="note" style="color:#5E5A54;font-size:11px;margin-top:10px">&#128161; 分类颜色在 config.json 中设置。</p>
    <div class="footer" style="margin-top:12px">
      <button class="btn" id="closeModalBtn">取消</button>
      <button class="btn btn-p" id="saveConfigBtn">保存</button>
    </div>
  </div>
</div>

<script>
var DATA = __EMBEDDED_DATA__;
var CC = {'工作':'#7BA78E','娱乐':'#D4956B','浏览':'#7B9EC7','通讯':'#A78BB5','系统':'#6B6B6B','其他':'#5A5A5A'};
var chart = null, state = {range:'today',view:'cat',ctype:'donut',drill:null,hlKey:null};

function gf(s){var h=Math.floor(s/3600),m=Math.floor((s%3600)/60);return h?h+'h '+m+'m':m+'m';}

function items(){
  var r=state.range,v=state.view;
  if(v=='cat'&&!state.drill)return DATA[r].cat;
  if(v=='cat'&&state.drill){
    var pk='progs_by_cat_'+r,progs=(DATA[pk]||{})[state.drill]||[];
    return progs.map(function(p){return{label:p.process,value:p.total_seconds,color:p.color||CC[p.category]||'#888',icon_uri:p.icon_uri,hk:p.process,type:'program'};});
  }
  return DATA[r].prog;
}

function hkIdx(hk){
  var its=items();
  for(var i=0;i<its.length;i++)if(its[i].hk==hk)return i;
  return -1;
}

function totalVal(){return items().reduce(function(s,i){return s+i.value;},0);}

/* ── Center text plugin for donut chart ── */
var centerTextPlugin = {
  id:'centerText',
  afterDraw:function(chart){
    if(chart.config.type!='doughnut')return;
    var ctx=chart.ctx,its=items(),total=totalVal(),hl=state.hlKey;
    var activeItem=hl?its[hkIdx(hl)]:null;
    var displayTime=activeItem?gf(activeItem.value):gf(total);
    var displayLabel=activeItem?activeItem.label:'总计';
    var ca=chart.chartArea;
    ctx.save();
    ctx.textAlign='center';
    ctx.fillStyle='#EAE4D9';
    ctx.font='bold 20px Consolas,monospace';
    ctx.fillText(displayTime, ca.left+ca.width/2, ca.top+ca.height/2-4);
    ctx.fillStyle=activeItem?activeItem.color:'#5E5A54';
    ctx.font='11px Segoe UI,sans-serif';
    ctx.fillText(displayLabel, ca.left+ca.width/2, ca.top+ca.height/2+18);
    ctx.restore();
  }
};

/* ── Bar chart icon plugin ── */
var barIconPlugin = {
  id:'barIcon',
  afterDraw:function(chart){
    if(chart.config.type!='bar')return;
    var ctx=chart.ctx,meta=chart.getDatasetMeta(0),its=items(),ca=chart.chartArea;
    chart.data.labels.forEach(function(l,i){
      var bar=meta.data[i];if(!bar)return;
      var x=ca.left-28,y=bar.y;
      var item=its[i];if(!item||!item.icon_uri)return;
      if(state.view=='prog'||(state.view=='cat'&&state.drill)){
        var img=new Image();img.src=item.icon_uri;
        if(img.complete&&img.naturalWidth>0){ctx.drawImage(img,x,y-10,20,20);}
        else{ctx.fillStyle=item.color;ctx.beginPath();ctx.rect(x,y-10,20,20);ctx.fill();
          ctx.fillStyle='#fff';ctx.font='bold 11px Segoe UI,sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
          ctx.fillText((item.label||'?')[0],x+10,y);}
      }
    });
  }
};
Chart.register(centerTextPlugin, barIconPlugin);

/* ── Render chart ── */
function renderChart(){
  var its=items();
  document.querySelector('.chart-box').innerHTML='<canvas id="chartCanvas"></canvas>';
  var ctx=document.getElementById('chartCanvas').getContext('2d');
  if(chart)chart.destroy();
  var total=totalVal();
  var common={
    responsive:true,maintainAspectRatio:false,
    plugins:{
      legend:{display:false},
      tooltip:{
        backgroundColor:'#24262E',titleColor:'#EAE4D9',bodyColor:'#EAE4D9',
        borderColor:'#2E3039',borderWidth:1,padding:10,cornerRadius:6,
        callbacks:{
          title:function(t){return t[0].label;},
          label:function(t){return ' '+gf(t.raw)+' ('+Math.round(t.raw/total*100)+'%)';}
        }
      }
    }
  };
  if(state.ctype=='donut'){
    chart=new Chart(ctx,{
      type:'doughnut',
      data:{labels:its.map(function(i){return i.label;}),datasets:[{data:its.map(function(i){return i.value;}),backgroundColor:its.map(function(i){return i.color;}),borderWidth:1,borderColor:'#1E2027',hoverOffset:15}]},
      options:Object.assign(common,{
        cutout:'62%',
        animations:{animateRotate:true,duration:400},
        onHover:function(e,els){
          if(els.length){state.hlKey=its[els[0].index].hk;if(chart){chart.setActiveElements([{datasetIndex:0,index:els[0].index}]);chart.draw();}}
          else{state.hlKey=null;chart.setActiveElements([]);chart.draw();}
          syncHL();
        }
      })
    });
  }else{
    var isProgView=state.view=='prog'||(state.view=='cat'&&state.drill);
    var padLeft=isProgView?32:8;
    chart=new Chart(ctx,{
      type:'bar',
      data:{labels:its.map(function(i){
        // Category view: show text; Program view: empty (icon only via plugin)
        return (state.view=='cat'&&!state.drill)?i.label:'';
      }),datasets:[{data:its.map(function(i){return i.value;}),backgroundColor:its.map(function(i){return i.color;}),borderRadius:4,hoverBackgroundColor:its.map(function(i){return i.color;})}]},
      options:Object.assign(common,{
        indexAxis:'y',layout:{padding:{left:padLeft}},
        scales:{
          x:{grid:{color:'#2E3039'},ticks:{color:'#5E5A54'}},
          y:{ticks:{color:function(ctx){var its2=items();return ctx.chart.data.labels[0]?'#9B958A':'transparent';},font:{size:11}}}
        },
        onHover:function(e,els){
          if(els.length){state.hlKey=its[els[0].index].hk;if(chart){chart.setActiveElements([{datasetIndex:0,index:els[0].index}]);chart.draw();}}
          else{state.hlKey=null;chart.setActiveElements([]);chart.draw();}
          syncHL();
        }
      })
    });
  }
}

/* ── Highlight sync (does NOT re-render list, just toggles CSS) ── */
function syncHL(){
  var hl=state.hlKey;
  document.querySelectorAll('#breakdownList .bi').forEach(function(el){
    var isHL=hl&&hl===el.dataset.hk;
    el.classList.toggle('hl',isHL);
    el.classList.toggle('dimmed',hl&&!isHL);
  });
}

/* ── Render breakdown list (initial render only) ── */
function renderList(){
  var its=items(),total=totalVal();
  document.getElementById('breakdownList').innerHTML=its.map(function(i){
    var pct=total?Math.round(i.value/total*100):0;
    var dot='<div class="dot" style="width:10px;height:10px;border-radius:3px;flex-shrink:0;background:'+i.color+'"></div>';
    var icon='<img class="pgm-icon" src="'+i.icon_uri+'" alt="">';
    return '<div class="bi" data-hk="'+i.hk+'">'+(state.view=='cat'&&!state.drill?dot:icon)+'<div class="info"><div class="name">'+i.label+'</div></div><div class="bar-w"><div class="bar-f" style="width:'+Math.max(pct,2)+'%;background:'+i.color+'"></div></div><span class="tm">'+gf(i.value)+'</span><span class="pct">'+pct+'%</span></div>';
  }).join('');
  var list=document.querySelectorAll('#breakdownList .bi');
  list.forEach(function(el){
    el.onclick=function(){
      var hk=el.dataset.hk;
      if(state.view=='cat'&&!state.drill&&CC[hk]){state.drill=hk;document.getElementById('bread').style.display='inline-flex';renderChart();renderList();}
    };
    el.onmouseenter=function(){state.hlKey=el.dataset.hk;var idx=hkIdx(state.hlKey);if(idx>=0&&chart){chart.setActiveElements([{datasetIndex:0,index:idx}]);chart.draw();}syncHL();};
    el.onmouseleave=function(){state.hlKey=null;if(chart){chart.setActiveElements([]);chart.draw();}syncHL();};
  });
}

/* ── Timeline ── */
function renderTL(){
  var tl=DATA.timeline||[];
  document.getElementById('timeline').innerHTML=tl.map(function(r){
    var s=r.duration,ds=s>=3600?Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m':Math.floor(s/60)+'m';
    var cc=CC[r.category]||'#888';
    return '<div class="tr"><span class="tt">'+(r.started_at||'').slice(11,16)+'</span>'+(r.icon_uri?'<img class="pgm-icon" src="'+r.icon_uri+'" alt="" style="width:18px;height:18px">':'')+'<span class="ttl">'+r.process+' &mdash; '+(r.window_title||'').slice(0,30)+'</span><span class="td">'+ds+'</span><span class="tc" style="background:'+cc+'22;color:'+cc+'">'+r.category+'</span></div>';
  }).join('');
}

function refresh(){renderChart();renderList();renderTL();}

/* ── Events ── */
document.getElementById('timeTabs').addEventListener('click',function(e){
  var t=e.target.closest('.tab');if(!t||!t.dataset.r)return;
  document.querySelectorAll('#timeTabs .tab').forEach(function(x){x.classList.remove('active');});
  t.classList.add('active');state.range=t.dataset.r;state.drill=null;state.hlKey=null;
  document.getElementById('bread').style.display='none';refresh();
});
document.querySelector('#app .toolbar').addEventListener('click',function(e){
  var b=e.target.closest('.tb');if(!b)return;
  b.parentElement.querySelectorAll('.tb').forEach(function(x){x.classList.remove('active');});b.classList.add('active');
  if(b.dataset.v){state.view=b.dataset.v;state.drill=null;document.getElementById('bread').style.display='none';refresh();}
  if(b.dataset.c){state.ctype=b.dataset.c;refresh();}
});
document.getElementById('bread').onclick=function(){state.drill=null;this.style.display='none';refresh();};
document.getElementById('exportBtn').onclick=function(){
  var rows=DATA.timeline||[],csv='﻿进程,窗口标题,分类,开始时间,时长(秒)\n';
  rows.forEach(function(r){csv+=r.process+','+r.window_title+','+r.category+','+r.started_at+','+r.duration+'\n';});
  var a=document.createElement('a');a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);a.download='time_export.csv';a.click();
};

/* ── Settings: editable rules ── */
function openSettings(){
  var config=DATA.config,cats=Object.keys(config.categories||{});
  var body=document.getElementById('rulesBody');body.innerHTML='';
  (config.rules||[]).forEach(function(r,i){addRuleRow(r.process,r.title_pattern||'',r.category||'其他');});
  document.getElementById('settingsModal').classList.add('show');
}

function addRuleRow(process,titlePattern,category){
  var body=document.getElementById('rulesBody'),row=body.insertRow();
  var cats=Object.keys(DATA.config.categories||{});
  row.innerHTML='<td><input type="text" value="'+(process||'')+'" class="r-proc"></td>'+
    '<td><input type="text" value="'+(titlePattern||'')+'" class="r-pat" placeholder="留空=所有窗口"></td>'+
    '<td><select class="r-cat">'+cats.map(function(c){return '<option'+(c==category?' selected':'')+'>'+c+'</option>';}).join('')+'</select></td>'+
    '<td><button class="btn btn-r" style="padding:3px 10px;font-size:11px" onclick="this.closest(\'tr\').remove()">&#10005;</button></td>';
}

document.getElementById('gearBtn').onclick=openSettings;
document.getElementById('addRuleBtn').onclick=function(){addRuleRow('','','其他');};
document.getElementById('closeModalBtn').onclick=function(){document.getElementById('settingsModal').classList.remove('show');};
document.getElementById('settingsModal').onclick=function(e){if(e.target===this)this.classList.remove('show');};

document.getElementById('saveConfigBtn').onclick=function(){
  var rows=document.querySelectorAll('#rulesBody tr'),rules=[];
  rows.forEach(function(r){
    var proc=r.querySelector('.r-proc'),pat=r.querySelector('.r-pat'),cat=r.querySelector('.r-cat');
    if(proc&&proc.value.trim())rules.push({process:proc.value.trim(),title_pattern:pat.value.trim()||null,category:cat?cat.value:'其他'});
  });
  var config=DATA.config;config.rules=rules;
  fetch('/save-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)})
    .then(function(r){return r.json();})
    .then(function(resp){
      if(resp.ok){DATA.config=resp.config;}
      document.getElementById('settingsModal').classList.remove('show');
      refresh();
    });
};

refresh();
</script>
</body>
</html>"""
