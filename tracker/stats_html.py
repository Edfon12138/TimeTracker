"""Generate self-contained HTML stats page and open in browser."""
import os, json, sqlite3, webbrowser, tempfile, base64
from datetime import datetime, timedelta, date as dt_date
import storage, config as cfg, icon_extractor


def _icon_svg(letter: str, color: str, size: int = 20) -> str:
    """Generate a colored letter icon as an SVG data URI."""
    r = max(2, round(size * 0.18))
    fs = round(size * 0.55)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
        f'<rect width="{size}" height="{size}" rx="{r}" fill="{color}"/>'
        f'<text x="{size//2}" y="{size//2+fs*0.35}" text-anchor="middle" '
        f'fill="white" font-size="{fs}" font-weight="bold" '
        f'font-family="Segoe UI,sans-serif">{letter}</text></svg>'
    )
    return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"


def _add_icons(items: list) -> list:
    """Add icon_uri to each item based on its label/process name."""
    for item in items:
        label = item.get("label") or item.get("process", "")
        letter = (os.path.splitext(label)[0] or "?")[0].upper()
        color = item.get("color", "#888")
        item["icon_uri"] = _icon_svg(letter, color)
    return items


def _get_chart_data(view_mode: str, date_from: str, date_to: str, drill_cat=None):
    conf = cfg.load_config()
    cm = {c: conf["categories"].get(c, {}).get("color", "#5A5A5A") for c in conf["categories"]}
    if view_mode == "category" and not drill_cat:
        rows = storage.get_range_summary(date_from, date_to)
        return _add_icons([{"label": r["category"], "value": r["total_seconds"],
                            "color": cm.get(r["category"], "#5A5A5A"), "hk": r["category"],
                            "type": "category"} for r in rows])
    else:
        rows = storage.get_program_stats(date_from, date_to)
        return _add_icons([{"label": r["process"], "value": r["total_seconds"],
                            "color": icon_extractor.get_icon_color(r["process"]),
                            "hk": r["process"], "type": "program"} for r in rows])


def generate():
    today = dt_date.today().isoformat()
    week_start = (dt_date.today() - timedelta(days=dt_date.today().weekday())).isoformat()
    month_start = dt_date.today().replace(day=1).isoformat()

    data_pack = {
        "today": {"cat": _get_chart_data("category", today, today),
                  "prog": _get_chart_data("program", today, today)},
        "week": {"cat": _get_chart_data("category", week_start, today),
                 "prog": _get_chart_data("program", week_start, today)},
        "month": {"cat": _get_chart_data("category", month_start, today),
                  "prog": _get_chart_data("program", month_start, today)},
        "timeline": _add_icons([dict(r) for r in storage.get_activity_timeline(today)]),
        "config": cfg.load_config(),
    }

    # Per-category program data for drill-down
    conn = sqlite3.connect(storage._db_path())
    conn.row_factory = sqlite3.Row
    for rn, df, dt_ in [
        ("today", today, today),
        ("week", week_start, today),
        ("month", month_start, today),
    ]:
        rows = conn.execute(
            "SELECT process, category, SUM(duration) AS total_seconds "
            "FROM activity_log WHERE date BETWEEN ? AND ? "
            "GROUP BY process, category ORDER BY category, total_seconds DESC",
            (df, dt_)
        ).fetchall()
        grouped = {}
        for r in rows:
            d = dict(r)
            d["color"] = icon_extractor.get_icon_color(d["process"])
            grouped.setdefault(d["category"], []).append(d)
        # Add icons to each item in each category group
        for cat in grouped:
            _add_icons(grouped[cat])
        data_pack[f"progs_by_cat_{rn}"] = grouped
    conn.close()

    json_data = json.dumps(data_pack, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__EMBEDDED_DATA__", json_data)

    path = os.path.join(tempfile.gettempdir(), "timetracker_stats.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open(f"file://{path}")


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
.chart-box{width:300px;height:260px;position:relative;flex-shrink:0}
.breakdown{flex:1;min-width:240px;display:flex;flex-direction:column;gap:4px}
.bi{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;background:#24262E;cursor:pointer;transition:all .1s}
.bi:hover{background:#2C2E36;transform:translateX(2px)}
.bi.dimmed:not(.hl){opacity:.3}
.bi.hl{box-shadow:inset 0 0 0 1px rgba(212,149,107,.5);background:#2A2E35}
.pgm-icon{width:22px;height:22px;border-radius:4px;flex-shrink:0;display:inline-block;vertical-align:middle}
.info{flex:1;min-width:0}
.name{font-size:13px;color:#EAE4D9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar{width:60px;height:3px;background:#2E3039;border-radius:2px;overflow:hidden;flex-shrink:0}
.bar-f{height:100%;border-radius:2px;transition:width .2s}
.tm{font-family:Consolas,'Cascadia Code',monospace;font-size:14px;font-weight:500;color:#EAE4D9;width:56px;text-align:right;flex-shrink:0}
.pct{font-family:Consolas,monospace;font-size:11px;color:#5E5A54;width:32px;text-align:right;flex-shrink:0}
.sl{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#5E5A54;margin:16px 0 10px;display:flex;align-items:center;gap:8px}
.sl::after{content:'';flex:1;height:1px;background:#2E3039}
.tr{display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:4px;font-size:12px}
.tr:hover{background:#24262E}
.tt{font-family:Consolas,monospace;font-size:11px;color:#5E5A54;width:48px;flex-shrink:0}
.ttl{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.td{font-family:Consolas,monospace;font-size:12px;font-weight:500;color:#EAE4D9;width:52px;text-align:right;flex-shrink:0}
.tc{font-size:10px;padding:2px 8px;border-radius:3px;font-weight:500;width:42px;text-align:center;flex-shrink:0}
.footer{display:flex;gap:10px;justify-content:flex-end;margin-top:20px;padding-top:16px;border-top:1px solid #2E3039}
.btn{padding:7px 16px;border-radius:6px;font-size:12px;font-family:inherit;cursor:pointer;border:1px solid #2E3039;background:#24262E;color:#9B958A;transition:all .1s}
.btn:hover{color:#EAE4D9;border-color:#4A4D56}
.btn-p{background:#D4956B;color:#1A1C21;border-color:#D4956B;font-weight:600}
.btn-p:hover{background:#E8B48A}
.bread{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#D4956B;cursor:pointer}
.bread:hover{color:#E8B48A}
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center}
.modal-overlay.show{display:flex}
.modal{background:#1E2027;border:1px solid #2E3039;border-radius:12px;width:680px;max-height:80vh;overflow-y:auto;padding:24px}
.modal h2{font-size:16px;color:#EAE4D9;margin-bottom:16px}
.modal table{width:100%;border-collapse:collapse;font-size:12px}
.modal th{background:#2E3039;color:#9B958A;padding:8px 10px;text-align:left;font-weight:500;position:sticky;top:0}
.modal td{padding:8px 10px;border-bottom:1px solid #2E3039;color:#EAE4D9}
.modal tr:hover td{background:#24262E}
.modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.modal .note{color:#5E5A54;font-size:11px;margin-top:12px}
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

<!-- Settings Modal -->
<div class="modal-overlay" id="settingsModal">
  <div class="modal">
    <h2>分类规则设置</h2>
    <table><thead><tr><th>进程</th><th>标题匹配(正则)</th><th>分类</th></tr></thead><tbody id="rulesBody"></tbody></table>
    <p class="note">&#128161; 要修改规则，在右键托盘菜单「设置」中打开 config.json 编辑。</p>
    <div class="modal-actions">
      <button class="btn btn-p" id="closeModalBtn">关闭</button>
    </div>
  </div>
</div>

<script>
var DATA = __EMBEDDED_DATA__;
var CC = {'工作':'#7BA78E','娱乐':'#D4956B','浏览':'#7B9EC7','通讯':'#A78BB5','系统':'#6B6B6B','其他':'#5A5A5A'};
var chart = null, state = {range:'today',view:'cat',ctype:'donut',drill:null,hlIdx:-1};

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

function getIdxByHk(hk){
  var its=items();
  for(var i=0;i<its.length;i++)if(its[i].hk==hk)return i;
  return -1;
}

// Custom Chart.js plugin: draw letter icons on bar chart y-axis
var iconLabelPlugin = {
  id:'iconLabel',
  afterDraw:function(chart){
    if(chart.config.type!='bar'||chart.data.datasets.length==0)return;
    var ctx=chart.ctx,meta=chart.getDatasetMeta(0);
    var its=items();
    chart.data.labels.forEach(function(l,i){
      var bar=meta.data[i];if(!bar)return;
      var x=chart.chartArea.left-26,y=bar.y;
      var item=its[i];if(!item)return;
      var img=new Image();img.src=item.icon_uri;
      // Draw icon as img if available, fallback to colored square
      if(img.complete&&img.naturalWidth>0){
        ctx.drawImage(img,x,y-10,20,20);
      }else{
        ctx.fillStyle=item.color||'#888';
        ctx.beginPath();ctx.roundRect?ctx.roundRect(x,y-10,20,20,4):ctx.rect(x,y-10,20,20);
        ctx.fill();
        ctx.fillStyle='#fff';
        ctx.font='bold 11px Segoe UI,sans-serif';
        ctx.textAlign='center';ctx.textBaseline='middle';
        ctx.fillText((item.label||'?')[0],x+10,y);
      }
    });
  }
};

Chart.register(iconLabelPlugin);

function renderChart(){
  var its=items();
  var container=document.querySelector('.chart-box');
  container.innerHTML='<canvas id="chartCanvas"></canvas>';
  var ctx=document.getElementById('chartCanvas').getContext('2d');
  if(chart)chart.destroy();

  var commonOpts={
    responsive:true,maintainAspectRatio:false,
    plugins:{
      legend:{display:false},
      tooltip:{
        backgroundColor:'#24262E',titleColor:'#EAE4D9',
        bodyColor:'#EAE4D9',borderColor:'#2E3039',borderWidth:1,
        padding:10,cornerRadius:6,
        callbacks:{
          title:function(t){return t[0].label;},
          label:function(t){
            var total=t.dataset.data.reduce(function(a,b){return a+b;},0);
            return ' '+gf(t.raw)+' ('+Math.round(t.raw/total*100)+'%)';
          }
        }
      }
    }
  };

  if(state.ctype=='donut'){
    chart=new Chart(ctx,{
      type:'doughnut',
      data:{labels:its.map(function(i){return i.label;}),datasets:[{data:its.map(function(i){return i.value;}),backgroundColor:its.map(function(i){return i.color;}),borderWidth:0,hoverOffset:12}]},
      options:Object.assign(commonOpts,{
        cutout:'65%',
        onHover:function(e,els){
          state.hlIdx=els.length?els[0].index:-1;
          state._hl=state.hlIdx>=0?its[state.hlIdx].hk:null;
          if(state.hlIdx>=0&&chart){chart.setActiveElements([{datasetIndex:0,index:state.hlIdx}]);chart.draw();}
          renderList();
        }
      })
    });
  }else{
    // For bar chart, extend labels area to make room for icons
    chart=new Chart(ctx,{
      type:'bar',
      data:{labels:its.map(function(i){return i.label;}),datasets:[{data:its.map(function(i){return i.value;}),backgroundColor:its.map(function(i){return i.color;}),borderRadius:3,hoverBackgroundColor:its.map(function(i){return i.color;})}]},
      options:Object.assign(commonOpts,{
        indexAxis:'y',
        layout:{padding:{left:30}},
        scales:{
          x:{grid:{color:'#2E3039'},ticks:{color:'#5E5A54'}},
          y:{
            ticks:{
              color:'#9B958A',font:{size:11},
              callback:function(v,i){return its[i]?' '+its[i].label:'';}
            }
          }
        },
        onHover:function(e,els){
          state.hlIdx=els.length?els[0].index:-1;
          state._hl=state.hlIdx>=0?its[state.hlIdx].hk:null;
          if(state.hlIdx>=0&&chart){chart.setActiveElements([{datasetIndex:0,index:state.hlIdx}]);chart.draw();}
          renderList();
        }
      })
    });
  }
}

function renderList(){
  var its=items(),total=its.reduce(function(s,i){return s+i.value;},0),hl=state._hl;
  document.getElementById('breakdownList').innerHTML=its.map(function(i,idx){
    var pct=total?Math.round(i.value/total*100):0;
    var isHL=hl&&hl===i.hk;var dim=hl&&hl!==i.hk;
    var cls=(isHL?' bi hl':'')+(dim?' dimmed':'');
    var icon='<img class="pgm-icon" src="'+i.icon_uri+'" alt="">';
    var dot=state.view=='cat'&&!state.drill?'<div class="dot" style="background:'+i.color+';width:10px;height:10px;border-radius:3px;flex-shrink:0"></div>':'';
    return '<div class="bi'+cls+'" data-hk="'+i.hk+'">'+(dot||icon)+'<div class="info"><div class="name">'+i.label+'</div></div><div class="bar"><div class="bar-f" style="width:'+Math.max(pct,2)+'%;background:'+i.color+'"></div></div><span class="tm">'+gf(i.value)+'</span><span class="pct">'+pct+'%</span></div>';
  }).join('');

  document.querySelectorAll('#breakdownList .bi').forEach(function(el){
    el.onclick=function(){
      var hk=el.dataset.hk;
      if(state.view=='cat'&&!state.drill&&CC[hk]){state.drill=hk;document.getElementById('bread').style.display='inline-flex';renderChart();renderList();}
    };
    el.onmouseenter=function(){state._hl=el.dataset.hk;state.hlIdx=getIdxByHk(state._hl);if(state.hlIdx>=0&&chart){chart.setActiveElements([{datasetIndex:0,index:state.hlIdx}]);chart.draw();}renderList();};
    el.onmouseleave=function(){state._hl=null;state.hlIdx=-1;if(chart){chart.setActiveElements([]);chart.draw();}renderList();};
  });
}

function renderTL(){
  var tl=DATA.timeline||[];
  document.getElementById('timeline').innerHTML=tl.map(function(r){
    var s=r.duration,ds=s>=3600?Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m':Math.floor(s/60)+'m';
    var cc=CC[r.category]||'#888';
    var itemIcon=r.icon_uri||'';
    return '<div class="tr">'+'<span class="tt">'+(r.started_at||'').slice(11,16)+'</span>'+(itemIcon?'<img class="pgm-icon" src="'+itemIcon+'" alt="" style="width:18px;height:18px">':'')+'<span class="ttl">'+r.process+' &mdash; '+(r.window_title||'').slice(0,30)+'</span><span class="td">'+ds+'</span><span class="tc" style="background:'+cc+'22;color:'+cc+'">'+r.category+'</span></div>';
  }).join('');
}

function refresh(){renderChart();renderList();renderTL();}

// Tab switching
document.getElementById('timeTabs').addEventListener('click',function(e){
  var t=e.target.closest('.tab');if(!t||!t.dataset.r)return;
  document.querySelectorAll('#timeTabs .tab').forEach(function(x){x.classList.remove('active');});
  t.classList.add('active');state.range=t.dataset.r;state.drill=null;state.hlIdx=-1;
  document.getElementById('bread').style.display='none';refresh();
});

// Toolbar: view + chart toggles
document.querySelector('#app .toolbar').addEventListener('click',function(e){
  var b=e.target.closest('.tb');if(!b)return;
  var p=b.parentElement;p.querySelectorAll('.tb').forEach(function(x){x.classList.remove('active');});
  b.classList.add('active');
  if(b.dataset.v){state.view=b.dataset.v;state.drill=null;document.getElementById('bread').style.display='none';refresh();}
  if(b.dataset.c){state.ctype=b.dataset.c;refresh();}
});

// Breadcrumb back
document.getElementById('bread').onclick=function(){state.drill=null;this.style.display='none';refresh();};

// CSV export
document.getElementById('exportBtn').onclick=function(){
  var rows=DATA.timeline||[],csv='﻿进程,窗口标题,分类,开始时间,时长(秒)\n';
  rows.forEach(function(r){csv+=r.process+','+r.window_title+','+r.category+','+r.started_at+','+r.duration+'\n';});
  var a=document.createElement('a');a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);a.download='time_export.csv';a.click();
};

// Gear: show rules modal
document.getElementById('gearBtn').onclick=function(){
  var rules=DATA.config.rules||[],cats=DATA.config.categories||{};
  document.getElementById('rulesBody').innerHTML=rules.map(function(r){
    var tp=r.title_pattern||'';
    return '<tr><td>'+r.process+'</td><td>'+(tp?'<code style="color:#D4956B">'+tp+'</code>':'<span style="color:#5E5A54">所有窗口</span>')+'</td><td><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:'+((cats[r.category]||{}).color||'#888')+';vertical-align:middle;margin-right:4px"></span> '+r.category+'</td></tr>';
  }).join('');
  document.getElementById('settingsModal').classList.add('show');
};

document.getElementById('closeModalBtn').onclick=function(){document.getElementById('settingsModal').classList.remove('show');};
document.getElementById('settingsModal').onclick=function(e){if(e.target===this)this.classList.remove('show');};

refresh();
</script>
</body>
</html>"""
