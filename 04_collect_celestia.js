import path from 'node:path';
import {CELENIUM_API,DATA_DIR,STATE_DIR} from './config.js';
import {Checkpoint,NdjsonWriter,fetchWithRetry,saveJsonAtomic,sleep} from './lib/util.js';
const FROM=Number(process.env.CEL_FROM||'1698710400');
const NOW=Math.floor(Date.now()/1000);
const RATE=Number(process.env.RATE_MS||'250');
const HEADERS={'user-agent':'Mozilla/5.0 (X11; Linux x86_64) blob-da-market-pipeline/1.0 research','accept':'application/json'};
async function tryTemplates(urls){for(const u of urls){try{const r=await fetchWithRetry(u,{headers:HEADERS},{retries:4});const arr=Array.isArray(r)?r:(Array.isArray(r?.data)?r.data:null);if(arr)return arr;}catch{}await sleep(150);}return null;}
async function collectRollups(){const out=[];for(let o=0;;o+=100){const r=await fetchWithRetry(`${CELENIUM_API}/rollup?limit=100&offset=${o}`,{headers:HEADERS},{retries:5});const arr=Array.isArray(r)?r:(Array.isArray(r?.data)?r.data:[]);out.push(...arr);if(arr.length<100)break;await sleep(RATE);}
saveJsonAtomic(path.join(DATA_DIR,'raw','celestia','rollups.json'),out);console.log('rollups:',out.length);return out;}
async function collectSeries(){for(const name of['blobs_size','blobs_count','fee']){const pts=[];for(let f=FROM;f<NOW;f+=15552000){const t=Math.min(f+15552000,NOW);const arr=await tryTemplates([`${CELENIUM_API}/stats/series/${name}/day?from=${f}&to=${t}`,`${CELENIUM_API}/stats/series?name=${name}&timeframe=day&from=${f}&to=${t}`]);if(arr)pts.push(...arr);await sleep(RATE);}
saveJsonAtomic(path.join(DATA_DIR,'raw','celestia','series_'+name+'.json'),pts);console.log('series',name,':',pts.length,'points');}}
async function collectPerRollup(rollups){const cp=new Checkpoint(path.join(STATE_DIR,'celestia_rollups.json'),{idx:0});const w=new NdjsonWriter(path.join(DATA_DIR,'raw','celestia','rollup_daily.ndjson'));
for(let i=cp.state.idx;i<rollups.length;i++){const ru=rollups[i];const id=ru.id??ru.rollup_id;const slug=ru.slug||ru.name||String(id);if(id==null){cp.state.idx=i+1;cp.save();continue;}
for(const metric of['size','blobs_count','fee']){const arr=await tryTemplates([`${CELENIUM_API}/rollup/${id}/stats/${metric}/day?from=${FROM}&to=${NOW}`,`${CELENIUM_API}/rollup/${id}/stats?name=${metric}&timeframe=day&from=${FROM}&to=${NOW}`]);if(arr)for(const pt of arr){w.write({rollup_id:id,slug,metric,time:pt.time??pt.ts??pt.date??pt.bucket,value:pt.value??pt.amount??pt.sum??pt.count});}await sleep(RATE);}
cp.state.idx=i+1;cp.save();if(i%10===0)console.log('rollup',i+1,'/',rollups.length,slug);}
w.close();console.log('per-rollup daily done');}
async function main(){const rollups=await collectRollups();await collectSeries();await collectPerRollup(rollups);console.log('done');}
main().catch(e=>{console.error(e);process.exit(1);});
