"""Web 面板单页 HTML（零依赖内联：vanilla JS + inline CSS，无构建/无 vendor）。

0 外链纪律（D09）：页面不得含任何 http:// / https:// 引用（无 CDN 字体/脚本/
图片，无 SVG xmlns）——tests/test_webapp.py 对整页 HTML 硬断言，改动本文件后
跑测试确认。
"""

PAGE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>食品标签合规审查面板</title>
<style>
  :root { --line:#d8dee6; --fail:#b3261e; --manual:#9a6700; --pass:#1a7f37; --ink:#1f2430; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, "Segoe UI", "Microsoft YaHei", sans-serif;
         color:var(--ink); background:#f5f7fa; }
  header { background:#123c6d; color:#fff; padding:18px 24px; }
  header h1 { margin:0 0 4px; font-size:20px; }
  header p { margin:0; font-size:12px; opacity:.85; }
  main { max-width: 960px; margin: 0 auto; padding: 16px; }
  .panel { background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; margin-bottom:16px; }
  label { display:block; font-size:13px; margin:10px 0 4px; }
  textarea { width:100%; font-family:inherit; font-size:13px; padding:8px; border:1px solid var(--line); border-radius:6px; }
  .row { display:flex; flex-wrap:wrap; gap:16px; align-items:center; margin-top:12px; }
  .row label { margin:0; }
  select, input[type=file] { font-size:13px; }
  button { background:#123c6d; color:#fff; border:0; border-radius:6px; padding:9px 22px; font-size:14px; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
  #msg { margin-top:10px; font-size:13px; }
  #msg.err { color:var(--fail); }
  .card { background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; margin-bottom:16px; }
  .card h2 { margin:0 0 10px; font-size:16px; }
  .stats span { display:inline-block; margin-right:14px; font-size:13px; }
  .stats b.fail { color:var(--fail); } .stats b.manual { color:var(--manual); } .stats b.pass { color:var(--pass); }
  table { border-collapse:collapse; width:100%; margin-top:10px; font-size:12.5px; }
  th, td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
  th { background:#eef2f7; }
  td.lvl-不合规 { color:var(--fail); font-weight:600; white-space:nowrap; }
  td.lvl-待人工确认 { color:var(--manual); font-weight:600; white-space:nowrap; }
  td.lvl-合规 { color:var(--pass); white-space:nowrap; }
  .muted { color:#66707f; font-size:12px; }
  .diff li { margin:4px 0; font-size:13px; }
</style>
</head>
<body>
<header>
  <h1>食品标签合规审查面板</h1>
  <p>GB 7718-2011 / GB 7718-2025 双标尺规则引擎 · 本地运行，页面 0 外链，断网可演示</p>
</header>
<main>
  <section class="panel">
    <label>上传标签文本文件（UTF-8）<input type="file" id="file"></label>
    <label>或直接粘贴标签全文<textarea id="text" rows="9" placeholder="粘贴预包装食品标签文本…"></textarea></label>
    <div class="row">
      <label>规则集
        <select id="ruleset">
          <option value="both">双标尺对照（2011 + 2025）</option>
          <option value="2011">仅 GB 7718-2011</option>
          <option value="2025">仅 GB 7718-2025</option>
        </select>
      </label>
      <label><input type="checkbox" id="llm"> 启用 LLM 兜底（需已配置 FOOD_LABEL_LLM_*，默认关闭）</label>
      <button id="go">开始审查</button>
    </div>
    <div id="msg"></div>
  </section>
  <section id="result"></section>
</main>
<script>
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML.split('"').join('&quot;').split(String.fromCharCode(39)).join('&#39;');}
function msg(t,isErr){var m=document.getElementById('msg');m.textContent=t||'';m.className=isErr?'err':'';}
function show(data){
  var h='';
  var fb=data.fallback||{};
  h+='<div class="card"><h2>审查概要</h2>'
   +'<div class="muted">引擎版本 v'+esc(data.engine_version)+' ｜ 规则集 '+esc((data.ruleset_ids||[]).join('、'))
   +' ｜ LLM 兜底：'+esc(fb.status||'off')+'</div>';
  if((data.warnings||[]).length){
    h+='<ul class="diff">'+data.warnings.map(function(w){return '<li>'+esc(w)+'</li>';}).join('')+'</ul>';
  }
  var nodes=(data.pipeline&&data.pipeline.nodes)||[];
  h+='<table><tr><th>节点</th><th>状态</th><th>耗时(ms)</th><th>说明</th></tr>'
   +nodes.map(function(n){return '<tr><td>'+esc(n.node)+'</td><td>'+esc(n.status)+'</td><td>'+esc(n.elapsed_ms)+'</td><td>'+esc(n.detail)+'</td></tr>';}).join('')
   +'</table></div>';
  Object.keys(data.results||{}).forEach(function(rid){
    var res=data.results[rid], st=res.stats||{};
    h+='<div class="card"><h2>'+esc(rid)+'</h2><div class="stats">'
     +'<span>检查 <b>'+esc(st.checked||0)+'</b></span>'
     +'<span>合规 <b class="pass">'+esc(st.pass||0)+'</b></span>'
     +'<span>不合规 <b class="fail">'+esc(st.fail||0)+'</b></span>'
     +'<span>待人工 <b class="manual">'+esc(st.manual||0)+'</b></span></div>';
    h+='<table><tr><th>级别</th><th>规则</th><th>说明</th><th>依据</th><th>建议</th><th>证据</th></tr>';
    (res.findings||[]).forEach(function(f){
      if(f.level==='合规'){return;}
      var ev=f.evidence||{};
      h+='<tr><td class="lvl-'+esc(f.level)+'">'+esc(f.level)+'</td>'
        +'<td>'+esc(f.rule_id)+'</td><td>'+esc(f.message)+'</td>'
        +'<td>'+esc(((f.basis||{}).standard||'')+' '+((f.basis||{}).clause||''))+'</td>'
        +'<td>'+esc(f.advice||'')+'</td>'
        +'<td class="muted">'+esc(ev.region||'')+'：'+esc(ev.quote||'（无）')+'</td></tr>';
    });
    h+='</table></div>';
  });
  if(data.dual_diff){
    var dd=data.dual_diff;
    h+='<div class="card"><h2>双标尺对照（'+esc(dd.baseline)+' → '+esc(dd.target)+'）</h2><ul class="diff">'
     +'<li>2025 新增不合规：'+esc((dd.new_fails||[]).join('、')||'无')+'</li>'
     +'<li>相对 2011 放宽/消除：'+esc((dd.resolved_fails||[]).join('、')||'无')+'</li></ul></div>';
  }
  document.getElementById('result').innerHTML=h;
}
document.getElementById('go').addEventListener('click',function(){
  var btn=this; btn.disabled=true; msg('审查中…');
  var fileInput=document.getElementById('file');
  var text=document.getElementById('text').value;
  if(!fileInput.files.length && !text.trim()){msg('请上传标签文本文件或粘贴标签全文',true);btn.disabled=false;return;}
  var fd=new FormData();
  if(fileInput.files.length){fd.append('file',fileInput.files[0]);}
  else{fd.append('text',text);}
  fd.append('ruleset',document.getElementById('ruleset').value);
  fd.append('llm',document.getElementById('llm').checked?'true':'false');
  fetch('/api/check',{method:'POST',body:fd})
    .then(function(r){return r.json().then(function(j){return {ok:r.ok,body:j};});})
    .then(function(res){
      if(!res.ok){msg('请求失败：'+((res.body||{}).error||'未知错误'),true);return;}
      document.getElementById('result').innerHTML='';
      show(res.body); msg('');
    })
    .catch(function(e){msg('请求异常：'+e,true);})
    .then(function(){btn.disabled=false;});
});
</script>
</body>
</html>
"""
