
const cache = new Map();

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type !== "PROCESS_IMAGE_SELECTIVE") return;

  (async () => {
    try {
      const result = await processImage(msg.url, msg.profile, msg.strength);
      sendResponse({ok:true, dataUrl:result});
    } catch (err) {
      console.warn("[ColorAssist] image processing failed:", err);
      sendResponse({ok:false, error:String(err)});
    }
  })();

  return true;
});

function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }

function circularDistance(h, center) {
  const d=Math.abs(h-center)%360;
  return Math.min(d,360-d);
}

function rgbToHsl(r,g,b){
  r/=255; g/=255; b/=255;
  const max=Math.max(r,g,b), min=Math.min(r,g,b);
  let h=0, s=0;
  const l=(max+min)/2;

  if(max!==min){
    const d=max-min;
    s=l>.5 ? d/(2-max-min) : d/(max+min);
    if(max===r) h=(g-b)/d+(g<b?6:0);
    else if(max===g) h=(b-r)/d+2;
    else h=(r-g)/d+4;
    h*=60;
  }
  return [h,s*100,l*100];
}

function hslToRgb(h,s,l){
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

  return [
    Math.round((rp+m)*255),
    Math.round((gp+m)*255),
    Math.round((bp+m)*255)
  ];
}

function weightsFromProfile(profile){
  const m=profile?.metrics || {};
  return {
    protan: clamp((m.protan?.confusion ?? 0)/100,0,1),
    deutan: clamp((m.deutan?.confusion ?? 0)/100,0,1),
    tritan: clamp((m.tritan?.confusion ?? 0)/100,0,1)
  };
}

function selectiveTransform(r,g,b,profile,strength){
  const [h0,s0,l0]=rgbToHsl(r,g,b);

  // 저채도/거의 검정/거의 흰색은 보정하지 않음
  if(s0 < 28 || l0 < 7 || l0 > 95) return null;

  const w=weightsFromProfile(profile);
  const rg=Math.max(w.protan,w.deutan);
  const by=w.tritan;

  // 정상 색각에 가까운 사용자가 수동으로 강도를 올렸을 때도 테스트 가능하게,
  // 가장 높은 축에 최소 가중치를 부여
  let p={...w};
  if(strength > 0.15){
    const entries=Object.entries(p).sort((a,b)=>b[1]-a[1]);
    if(entries[0][1] < 0.35) p[entries[0][0]] = 0.55;
  }

  const rg2=Math.max(p.protan,p.deutan);
  const by2=p.tritan;

  const redRel=Math.max(0,1-circularDistance(h0,0)/48);
  const greenRel=Math.max(0,1-circularDistance(h0,125)/55);
  const yellowRel=Math.max(0,1-circularDistance(h0,58)/34);
  const blueRel=Math.max(0,1-circularDistance(h0,220)/46);

  let h=h0, s=s0, l=l0, relevance=0;

  if(rg2>0){
    if(redRel>.28){
      const k=redRel*rg2*strength;
      h += 30*k;
      s = clamp(s + 14*k,0,100);
      l = clamp(l - 3*k,0,100);
      relevance=Math.max(relevance,k);
    }else if(greenRel>.28){
      const k=greenRel*rg2*strength;
      h += 52*k;
      s = clamp(s + 12*k,0,100);
      l = clamp(l + 3*k,0,100);
      relevance=Math.max(relevance,k);
    }
  }

  if(by2>0){
    if(blueRel>.28){
      const k=blueRel*by2*strength;
      h += 32*k;
      s = clamp(s + 13*k,0,100);
      relevance=Math.max(relevance,k);
    }else if(yellowRel>.28){
      const k=yellowRel*by2*strength;
      h -= 24*k;
      s = clamp(s + 12*k,0,100);
      relevance=Math.max(relevance,k);
    }
  }

  // 혼동축과 충분히 관련된 픽셀만 변경
  if(relevance < 0.10) return null;

  const [nr,ng,nb]=hslToRgb(h,s,l);
  return [nr,ng,nb];
}

async function processImage(url, profile, strengthPct){
  const strength=clamp(Number(strengthPct || profile?.correctionStrength || 0)/100,0,1);
  if(!url || strength<=0) return null;

  const cacheKey=JSON.stringify([
    url,
    Math.round(strength*100),
    profile?.dominantAxis,
    profile?.metrics?.protan?.confusion,
    profile?.metrics?.deutan?.confusion,
    profile?.metrics?.tritan?.confusion
  ]);

  if(cache.has(cacheKey)) return cache.get(cacheKey);

  const res=await fetch(url, {credentials:"omit", cache:"force-cache"});
  if(!res.ok) throw new Error(`HTTP ${res.status}`);

  const blob=await res.blob();
  const bitmap=await createImageBitmap(blob);

  // 너무 큰 이미지는 브라우저 성능 보호를 위해 축소
  const maxDim=1400;
  const scale=Math.min(1, maxDim/Math.max(bitmap.width,bitmap.height));
  const w=Math.max(1,Math.round(bitmap.width*scale));
  const h=Math.max(1,Math.round(bitmap.height*scale));

  const canvas=new OffscreenCanvas(w,h);
  const ctx=canvas.getContext("2d",{willReadFrequently:true});
  ctx.drawImage(bitmap,0,0,w,h);

  const img=ctx.getImageData(0,0,w,h);
  const data=img.data;

  let changed=0;
  for(let i=0;i<data.length;i+=4){
    if(data[i+3] < 12) continue;

    const out=selectiveTransform(
      data[i],data[i+1],data[i+2],
      profile,strength
    );

    if(out){
      data[i]=out[0];
      data[i+1]=out[1];
      data[i+2]=out[2];
      changed++;
    }
  }

  // 보정 대상 픽셀이 사실상 없으면 원본 사용
  if(changed < (w*h)*0.003){
    cache.set(cacheKey,null);
    return null;
  }

  ctx.putImageData(img,0,0);
  const outBlob=await canvas.convertToBlob({type:"image/webp",quality:.92});
  const arr=new Uint8Array(await outBlob.arrayBuffer());

  let binary="";
  const chunk=0x8000;
  for(let i=0;i<arr.length;i+=chunk){
    binary += String.fromCharCode(...arr.subarray(i,i+chunk));
  }
  const dataUrl=`data:${outBlob.type};base64,${btoa(binary)}`;

  // 간단 캐시 크기 제한
  if(cache.size>120) cache.clear();
  cache.set(cacheKey,dataUrl);
  return dataUrl;
}
