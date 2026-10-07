
(() => {
  const STYLE_ID = "__color_assist_style__";
  const CHANGED_ATTR = "data-color-assist-changed";
  const original = new Map();

  let settings = {
    enabled: true,
    visualCues: true,
    imageCorrection: true,
    manualStrength: null,
    colorVisionProfile: null
  };

  let observer = null;
  let debounceTimer = null;

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      [${CHANGED_ATTR}="shape"] {
        outline: 3px solid var(--color-assist-outline, rgba(15,23,42,.78)) !important;
        outline-offset: 1px !important;
      }
    `;
    document.documentElement.appendChild(style);
  }

  function remember(el) {
    if (original.has(el)) return;
    original.set(el, {
      color: el.style.color,
      backgroundColor: el.style.backgroundColor,
      borderTopColor: el.style.borderTopColor,
      borderRightColor: el.style.borderRightColor,
      borderBottomColor: el.style.borderBottomColor,
      borderLeftColor: el.style.borderLeftColor,
      filter: el.style.filter,
      src: el.tagName === "IMG" ? el.getAttribute("src") : null,
      srcset: el.tagName === "IMG" ? el.getAttribute("srcset") : null,
      changed: el.getAttribute(CHANGED_ATTR),
      outlineVar: el.style.getPropertyValue("--color-assist-outline")
    });
  }

  function restore() {
    for (const [el, s] of original.entries()) {
      if (!el?.isConnected) continue;
      el.style.color = s.color;
      el.style.backgroundColor = s.backgroundColor;
      el.style.borderTopColor = s.borderTopColor;
      el.style.borderRightColor = s.borderRightColor;
      el.style.borderBottomColor = s.borderBottomColor;
      el.style.borderLeftColor = s.borderLeftColor;
      el.style.filter = s.filter;

      if (el.tagName === "IMG" && s.src != null) {
        el.setAttribute("src", s.src);
        if (s.srcset) el.setAttribute("srcset", s.srcset);
        else el.removeAttribute("srcset");
        delete el.dataset.colorAssistImageSig;
        delete el.dataset.colorAssistOriginalSrc;
        delete el.dataset.colorAssistOriginalSrcset;
        delete el.dataset.colorAssistProcessing;
      }

      if (s.changed == null) el.removeAttribute(CHANGED_ATTR);
      else el.setAttribute(CHANGED_ATTR, s.changed);

      if (s.outlineVar) el.style.setProperty("--color-assist-outline", s.outlineVar);
      else el.style.removeProperty("--color-assist-outline");
    }
    original.clear();
  }

  function parseRgb(value) {
    if (!value || value === "transparent") return null;
    const m = value.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)/i);
    if (!m) return null;
    return {
      r: +m[1],
      g: +m[2],
      b: +m[3],
      a: m[4] == null ? 1 : +m[4]
    };
  }

  function rgbToHsl({r,g,b,a=1}) {
    r/=255; g/=255; b/=255;
    const max=Math.max(r,g,b), min=Math.min(r,g,b);
    let h=0, s=0;
    const l=(max+min)/2;

    if (max!==min) {
      const d=max-min;
      s=l>.5 ? d/(2-max-min) : d/(max+min);
      if (max===r) h=(g-b)/d+(g<b?6:0);
      else if (max===g) h=(b-r)/d+2;
      else h=(r-g)/d+4;
      h*=60;
    }
    return {h,s:s*100,l:l*100,a};
  }

  function hslToRgb({h,s,l,a=1}) {
    h=((h%360)+360)%360;
    s/=100; l/=100;

    const c=(1-Math.abs(2*l-1))*s;
    const x=c*(1-Math.abs((h/60)%2-1));
    const m=l-c/2;

    let rp=0,gp=0,bp=0;
    if(h<60){rp=c;gp=x}
    else if(h<120){rp=x;gp=c}
    else if(h<180){gp=c;bp=x}
    else if(h<240){gp=x;bp=c}
    else if(h<300){rp=x;bp=c}
    else{rp=c;bp=x}

    return {
      r:Math.round((rp+m)*255),
      g:Math.round((gp+m)*255),
      b:Math.round((bp+m)*255),
      a
    };
  }

  function cssRgb(c) {
    return c.a < 1
      ? `rgba(${c.r}, ${c.g}, ${c.b}, ${c.a})`
      : `rgb(${c.r}, ${c.g}, ${c.b})`;
  }

  function relLum(c) {
    const channel = v => {
      v/=255;
      return v<=.04045 ? v/12.92 : Math.pow((v+.055)/1.055,2.4);
    };
    return .2126*channel(c.r)+.7152*channel(c.g)+.0722*channel(c.b);
  }

  function contrast(a,b) {
    const l1=relLum(a), l2=relLum(b);
    return (Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05);
  }

  function circularDistance(h, center) {
    const d=Math.abs(h-center)%360;
    return Math.min(d,360-d);
  }

  function getWeights() {
    const m=settings.colorVisionProfile?.metrics || {};
    return {
      protan: Math.max(0, Math.min(1, (m.protan?.confusion ?? 0)/100)),
      deutan: Math.max(0, Math.min(1, (m.deutan?.confusion ?? 0)/100)),
      tritan: Math.max(0, Math.min(1, (m.tritan?.confusion ?? 0)/100))
    };
  }

  function correctionStrength() {
    const profile=settings.colorVisionProfile;
    return Math.max(
      0,
      Math.min(1, (settings.manualStrength ?? profile?.correctionStrength ?? 0)/100)
    );
  }

  function correctColor(rgb) {
    if (!settings.colorVisionProfile || rgb.a===0) return null;

    const hsl=rgbToHsl(rgb);
    if (hsl.s<8 || hsl.l<8 || hsl.l>96) return null;

    const w=getWeights();
    const strength=correctionStrength();
    if (strength<=0) return null;

    let h=hsl.h, s=hsl.s, l=hsl.l, relevance=0;

    const redRel=Math.max(0,1-circularDistance(h,0)/55);
    const greenRel=Math.max(0,1-circularDistance(h,125)/65);
    const yellowRel=Math.max(0,1-circularDistance(h,58)/42);
    const blueRel=Math.max(0,1-circularDistance(h,220)/55);

    const rgWeight=Math.max(w.protan,w.deutan);

    if (rgWeight>0) {
      if (redRel>.12) {
        const k=redRel*rgWeight*strength;
        h=h+34*k;
        s=Math.min(100,s+18*k);
        l=Math.max(18,l-4*k);
        relevance=Math.max(relevance,k);
      } else if (greenRel>.12) {
        const k=greenRel*rgWeight*strength;
        h=h+62*k;
        s=Math.min(100,s+14*k);
        l=Math.min(88,l+4*k);
        relevance=Math.max(relevance,k);
      }
    }

    if (w.tritan>0) {
      if (blueRel>.12) {
        const k=blueRel*w.tritan*strength;
        h=h+38*k;
        s=Math.min(100,s+16*k);
        relevance=Math.max(relevance,k);
      } else if (yellowRel>.12) {
        const k=yellowRel*w.tritan*strength;
        h=h-28*k;
        s=Math.min(100,s+15*k);
        relevance=Math.max(relevance,k);
      }
    }

    if (relevance<.08) return null;
    return {rgb:hslToRgb({h,s,l,a:rgb.a}), relevance};
  }

  function meaningfulColor(value) {
    const c=parseRgb(value);
    if (!c || c.a<.08) return null;
    return c;
  }

  function isReasonableTarget(el) {
    const r=el.getBoundingClientRect();
    if (r.width<2 || r.height<2) return false;

    if (["SCRIPT","STYLE","NOSCRIPT","SVG","PATH","VIDEO","CANVAS"].includes(el.tagName)) return false;
    return true;
  }

  async function applyMediaFilter(el) {
    if (!settings.imageCorrection || !settings.colorVisionProfile) return false;
    if (el.tagName !== "IMG") return false;

    const rect=el.getBoundingClientRect();
    if (rect.width<28 || rect.height<28) return false;

    const src = el.currentSrc || el.src;
    if (!src || src.startsWith("data:") || src.startsWith("blob:")) return false;

    const profile=settings.colorVisionProfile;
    const strength=Math.max(
      0,
      Math.min(100, settings.manualStrength ?? profile?.correctionStrength ?? 0)
    );

    const signature = [
      src,
      strength,
      profile?.dominantAxis,
      profile?.metrics?.protan?.confusion,
      profile?.metrics?.deutan?.confusion,
      profile?.metrics?.tritan?.confusion
    ].join("|");

    if (el.dataset.colorAssistImageSig === signature) return false;
    if (el.dataset.colorAssistProcessing === "1") return false;

    el.dataset.colorAssistProcessing="1";

    try{
      const response=await chrome.runtime.sendMessage({
        type:"PROCESS_IMAGE_SELECTIVE",
        url:src,
        profile,
        strength
      });

      if(response?.ok && response.dataUrl){
        remember(el);

        if(!el.dataset.colorAssistOriginalSrc){
          el.dataset.colorAssistOriginalSrc=el.src;
          el.dataset.colorAssistOriginalSrcset=el.getAttribute("srcset") || "";
        }

        el.src=response.dataUrl;
        el.removeAttribute("srcset");
        el.dataset.colorAssistImageSig=signature;
        return true;
      }
    }catch(e){
      // 외부 이미지 정책/포맷 문제는 원본 유지
    }finally{
      delete el.dataset.colorAssistProcessing;
    }

    return false;
  }

  function markChangedShape(el, outlineColor) {
    if (!settings.visualCues) return;

    const rect=el.getBoundingClientRect();
    if (rect.width<18 || rect.height<16) return;

    const tag=el.tagName;
    const role=el.getAttribute("role") || "";
    const text=(el.innerText || "").trim().replace(/\s+/g," ");

    const directShape =
      ["BUTTON","INPUT","SELECT","OPTION"].includes(tag) ||
      ["button","status","option","tab","checkbox","radio"].includes(role);

    const compactShape =
      ["A","SPAN","DIV","TD","LI"].includes(tag) &&
      rect.width<=360 &&
      rect.height<=140 &&
      text.length<=70;

    if (!directShape && !compactShape) return;

    remember(el);
    el.setAttribute(CHANGED_ATTR,"shape");
    el.style.setProperty(
      "--color-assist-outline",
      outlineColor || "rgba(15,23,42,.82)"
    );
  }

  function applyElement(el) {
    if (!(el instanceof HTMLElement) || !isReasonableTarget(el)) return;

    // Google 이미지 검색처럼 실제 <img> 요소는 별도 이미지 필터로 보정.
    if (el.tagName === "IMG") {
      applyMediaFilter(el);
      return;
    }

    const cs=getComputedStyle(el);
    const fg=meaningfulColor(cs.color);
    const bg=meaningfulColor(cs.backgroundColor);
    const borderVals=[
      cs.borderTopColor,
      cs.borderRightColor,
      cs.borderBottomColor,
      cs.borderLeftColor
    ];

    let textChanged=false;
    let shapeChanged=false;
    let outlineColor=null;

    const fgCorr=fg ? correctColor(fg) : null;
    const bgCorr=bg ? correctColor(bg) : null;

    if (fgCorr) {
      let ok=true;
      if (bg) {
        const before=contrast(fg,bg);
        const after=contrast(fgCorr.rgb,bg);
        if (after<3 && after<before) ok=false;
      }
      if (ok) {
        remember(el);
        el.style.color=cssRgb(fgCorr.rgb);
        textChanged=true;
      }
    }

    if (bgCorr) {
      let ok=true;
      if (fg) {
        const before=contrast(fg,bg);
        const after=contrast(fg,bgCorr.rgb);
        if (after<3 && after<before) ok=false;
      }
      if (ok) {
        remember(el);
        el.style.backgroundColor=cssRgb(bgCorr.rgb);
        shapeChanged=true;
        outlineColor=cssRgb(bgCorr.rgb);
      }
    }

    const borderProps=[
      "borderTopColor",
      "borderRightColor",
      "borderBottomColor",
      "borderLeftColor"
    ];

    borderVals.forEach((v,i)=>{
      const c=meaningfulColor(v);
      const corr=c ? correctColor(c) : null;
      if (corr) {
        remember(el);
        el.style[borderProps[i]]=cssRgb(corr.rgb);
        shapeChanged=true;
        outlineColor=outlineColor || cssRgb(corr.rgb);
      }
    });

    // 아이콘/패턴은 사용하지 않고,
    // 실제 배경색 또는 테두리색이 바뀐 요소의 외곽선만 굵게 표시한다.
    if (shapeChanged) {
      markChangedShape(el, outlineColor);
    }
  }

  function scan(root=document.body) {
    if (!settings.enabled || !settings.colorVisionProfile || !root) return;
    injectStyle();

    if (root instanceof HTMLElement) applyElement(root);

    const elements=root.querySelectorAll ? root.querySelectorAll("*") : [];
    const limit=Math.min(elements.length,7000);

    for (let i=0;i<limit;i++) {
      applyElement(elements[i]);
    }
  }

  function scheduleScan(root=document.body) {
    clearTimeout(debounceTimer);
    debounceTimer=setTimeout(()=>scan(root),220);
  }

  function startObserver() {
    if (observer) observer.disconnect();

    observer=new MutationObserver((mutations)=>{
      if (!settings.enabled) return;

      for (const m of mutations) {
        if (m.type==="childList" && m.addedNodes.length) {
          const node=[...m.addedNodes].find(n=>n instanceof HTMLElement);
          if (node) {
            scheduleScan(node);
            return;
          }
        }

        if (m.type==="attributes" && m.target instanceof HTMLElement) {
          if (
            m.attributeName === "src" &&
            m.target.tagName === "IMG" &&
            (m.target.getAttribute("src") || "").startsWith("data:")
          ) {
            continue;
          }
          scheduleScan(m.target);
          return;
        }
      }
    });

    if (document.body) {
      observer.observe(document.body,{
        subtree:true,
        childList:true,
        attributes:true,
        attributeFilter:["class","style","src"]
      });
    }
  }

  async function loadSettings() {
    settings=await chrome.storage.local.get({
      enabled:true,
      visualCues:true,
      imageCorrection:true,
      manualStrength:null,
      colorVisionProfile:null
    });
  }

  async function reapply() {
    restore();
    await loadSettings();

    if (settings.enabled) scan(document.body);
  }

  chrome.runtime.onMessage.addListener((msg,_sender,sendResponse)=>{
    (async()=>{
      if (msg.type==="SET_ENABLED") {
        settings.enabled=!!msg.value;
        if (!settings.enabled) restore();
        else await reapply();

      } else if (msg.type==="SET_VISUAL_CUES") {
        settings.visualCues=!!msg.value;
        await reapply();

      } else if (msg.type==="SET_IMAGE_CORRECTION") {
        settings.imageCorrection=!!msg.value;
        await reapply();

      } else if (msg.type==="SET_STRENGTH") {
        settings.manualStrength=Number(msg.value);
        await reapply();

      } else if (msg.type==="REANALYZE") {
        await reapply();

      } else if (msg.type==="RESTORE") {
        restore();
      }

      sendResponse({ok:true});
    })();

    return true;
  });

  chrome.storage.onChanged.addListener((_changes,area)=>{
    if (area==="local") {
      clearTimeout(debounceTimer);
      debounceTimer=setTimeout(()=>reapply(),180);
    }
  });

  (async()=>{
    await loadSettings();
    startObserver();

    if (settings.enabled && settings.colorVisionProfile) {
      scan(document.body);
    }
  })();
})();
