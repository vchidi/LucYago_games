(function(){
  var script=document.currentScript||{};
  var cfg={
    selector:script.dataset?script.dataset.titleSelector:"",
    title:script.dataset?script.dataset.titleName:"",
    orientation:script.dataset?script.dataset.orientation:"vertical",
    showCount:!(script.dataset&&script.dataset.showCount==="0")
  };
  if(!cfg.selector) return;

  var styleId="lucyago-reto-title-badge-style";
  if(!document.getElementById(styleId)){
    var style=document.createElement("style");
    style.id=styleId;
    style.textContent=[
      "#lucyagoRetoBar{display:none!important}",
      ".ly-reto-title-wrap{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;vertical-align:middle}",
      ".ly-reto-title-text{display:inline-block}",
      ".ly-reto-badge{display:inline-flex;align-items:center;justify-content:center;padding:7px 12px;border:0;border-radius:999px;background:linear-gradient(135deg,#ff006e 0%,#ffbe0b 52%,#21d4fd 100%);color:#fff;font:1000 15px/1 Arial,sans-serif;letter-spacing:.06em;text-transform:uppercase;box-shadow:0 6px 16px rgba(255,0,110,.34),inset 0 0 0 2px rgba(255,255,255,.42);text-shadow:0 1px 0 rgba(0,0,0,.28);cursor:pointer}",
      ".ly-reto-badge:hover{filter:saturate(1.15) brightness(1.04);transform:translateY(-1px)}",
      ".ly-reto-count,.ly-orientation-pill{display:inline-flex;align-items:center;justify-content:center;gap:5px;padding:6px 9px;border-radius:999px;background:#fff;color:#172033;font:1000 13px/1 Arial,sans-serif;box-shadow:inset 0 0 0 2px rgba(23,32,51,.11),0 3px 10px rgba(0,0,0,.08);white-space:nowrap}",
      ".ly-orientation-pill{width:40px;height:32px;padding:0;background:#eaf7ff;color:#125276;font-size:22px;line-height:1}",
      ".ly-tablet-emoji{display:inline-block;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',Arial,sans-serif;transform-origin:center center}",
      ".ly-tablet-emoji.horizontal{transform:rotate(90deg)}",
      "@media(max-width:760px){.ly-reto-title-wrap{gap:5px}.ly-reto-badge{font-size:12px;padding:6px 9px}.ly-reto-count,.ly-orientation-pill{font-size:11px;padding:5px 7px}}"
    ].join("\n");
    document.head.appendChild(style);
  }

  function params(){return new URLSearchParams(location.search);}
  function active(){return params().get("reto")==="1";}
  function removeOldBar(){
    document.querySelectorAll("#lucyagoRetoBar").forEach(function(el){el.remove();});
  }
  function getSession(){
    var p=params();
    var key=p.get("session")||"default";
    try{return JSON.parse(localStorage.getItem(key)||localStorage.getItem("lucyago_reto_"+key)||"{}");}
    catch(e){return {};}
  }
  function progress(){
    var p=params();
    var game=p.get("game")||"game";
    var target=parseInt(p.get("preguntas")||p.get("target")||"3",10)||3;
    var s=getSession();
    var r=s.results&&s.results[game]?s.results[game]:{};
    return {ok:Math.min(target,r.ok||0),bad:r.bad||0,target:target};
  }
  function goBack(){
    var p=params();
    var returnUrl=p.get("return")||"../reto_mixto.html";
    var sessionKey=p.get("session")||"default";
    location.href=returnUrl+"?continue=1&session="+encodeURIComponent(sessionKey);
  }
  function ensure(){
    removeOldBar();
    var anchor=document.querySelector(cfg.selector);
    if(!anchor) return;
    if(anchor.dataset.lyRetoReady==="1" && anchor.querySelector(".ly-reto-title-wrap")) return;

    var text=(cfg.title||anchor.textContent||"").trim();
    anchor.textContent="";
    anchor.dataset.lyRetoReady="1";

    var wrap=document.createElement("span");
    wrap.className="ly-reto-title-wrap";

    if(active()){
      var badge=document.createElement("button");
      badge.type="button";
      badge.className="ly-reto-badge";
      badge.textContent="RETO";
      badge.title="Volver al menu del reto";
      badge.setAttribute("aria-label","Volver al menu del reto");
      badge.addEventListener("click",goBack);
      wrap.appendChild(badge);
    }

    var title=document.createElement("span");
    title.className="ly-reto-title-text";
    title.textContent=text;
    wrap.appendChild(title);

    var orient=document.createElement("span");
    orient.className="ly-orientation-pill";
    var horizontal=cfg.orientation==="horizontal";
    orient.title=horizontal?"Horizontal":"Vertical";
    orient.setAttribute("aria-label",orient.title);
    var tablet=document.createElement("span");
    tablet.className="ly-tablet-emoji "+(horizontal?"horizontal":"vertical");
    tablet.textContent="\u{1F4F1}";
    tablet.setAttribute("aria-hidden","true");
    orient.appendChild(tablet);
    wrap.appendChild(orient);

    if(active()&&cfg.showCount){
      var count=document.createElement("span");
      count.className="ly-reto-count";
      count.dataset.lyRetoCounter="1";
      wrap.appendChild(count);
    }

    anchor.appendChild(wrap);
    update();
  }
  function update(){
    removeOldBar();
    var anchor=document.querySelector(cfg.selector);
    if(anchor && anchor.dataset.lyRetoReady==="1" && !anchor.querySelector(".ly-reto-title-wrap")){
      anchor.dataset.lyRetoReady="";
      ensure();
      return;
    }
    document.querySelectorAll("[data-ly-reto-counter='1']").forEach(function(el){
      var p=progress();
      el.textContent="\u2705 "+p.ok+"/"+p.target+" · \u274C "+p.bad;
    });
  }

  ensure();
  ["DOMContentLoaded","load","pageshow"].forEach(function(ev){
    window.addEventListener(ev,function(){setTimeout(ensure,0);},true);
  });
  window.addEventListener("storage",update);
  document.addEventListener("click",function(){setTimeout(update,80);},true);
  setInterval(function(){ensure();update();},700);
})();
