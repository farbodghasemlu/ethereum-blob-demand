import fs from 'node:fs';
import path from 'node:path';
import {GROWTHEPIE_API,GROWTHEPIE_EXPORTS,DATA_DIR} from './config.js';
import {CsvWriter,fetchWithRetry,saveJsonAtomic,sleep} from './lib/util.js';
const HEADERS={'user-agent':'Mozilla/5.0 (X11; Linux x86_64) blob-da-market-pipeline/1.0 research','accept':'application/json'};
const norm=d=>String(d).slice(0,10);
async function tryGet(url){try{return await fetchWithRetry(url,{headers:HEADERS},{retries:4,timeout:900000});}catch(e){console.log('  skip',url.split('/').pop(),String(e.message||e).slice(0,60));return null;}}
async function collectFundamentals(){const rows=new Map();
const full=await tryGet(`${GROWTHEPIE_API}/fundamentals.json`);
const add=r=>{if(!r||r.metric_key==null||r.origin_key==null||r.date==null||r.value==null)return;rows.set(`${r.metric_key}|${r.origin_key}|${norm(r.date)}`,[r.metric_key,r.origin_key,norm(r.date),r.value]);};
if(Array.isArray(full)){for(const r of full)add(r);console.log('fundamentals.json (last 90d):',full.length,'rows');}
for(const m of GROWTHEPIE_EXPORTS){const r=await tryGet(`${GROWTHEPIE_API}/export/${m}.json`);const arr=Array.isArray(r)?r:(Array.isArray(r?.data)?r.data:null);
if(arr){for(const x of arr)add(x);console.log('  export/'+m+'.json:',arr.length,'rows');}
await sleep(300);}
const file=path.join(DATA_DIR,'raw','growthepie','fundamentals.csv');fs.mkdirSync(path.dirname(file),{recursive:true});fs.rmSync(file,{force:true});
const w=new CsvWriter(file,['metric_key','origin_key','date','value']);
const sorted=[...rows.values()].sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:a[1]<b[1]?-1:a[1]>b[1]?1:a[2]<b[2]?-1:1);
for(const r of sorted)w.writeRow(r);w.close();
console.log('fundamentals total after dedupe:',sorted.length,'rows');return sorted.length;}
async function collectDaOverview(){const r=await tryGet(`${GROWTHEPIE_API}/da_overview.json`);
if(!r||!r.data){console.log('da_overview.json unavailable, skipping DA series');return 0;}
saveJsonAtomic(path.join(DATA_DIR,'raw','growthepie','da_overview.json'),r);
const metrics=r.data?.all_da?.metrics;
if(!metrics){console.log('da_overview.json has an unexpected shape, raw file saved for inspection');return 0;}
const file=path.join(DATA_DIR,'raw','growthepie','da_daily.csv');fs.rmSync(file,{force:true});
const w=new CsvWriter(file,['da_layer','metric','date','value','unit']);let n=0;
for(const[metric,layers]of Object.entries(metrics)){for(const[layer,obj]of Object.entries(layers)){const daily=obj?.daily;if(!daily||!Array.isArray(daily.data))continue;
const types=daily.types||[];const ui=types.indexOf('unix');
for(const row of daily.data){const ts=row[ui<0?0:ui];const date=new Date(Number(ts)>1e12?Number(ts):Number(ts)*1000).toISOString().slice(0,10);
for(let k=0;k<types.length;k++){if(k===ui)continue;if(row[k]==null)continue;w.writeRow([layer,metric,date,row[k],types[k]]);n++;}}}}
w.close();console.log('da_daily.csv:',n,'rows (daily DA series for Celestia, Ethereum blobs, EigenDA)');return n;}
async function main(){const a=await collectFundamentals();const b=await collectDaOverview();
if(a===0&&b===0){console.error('growthepie returned no usable data');process.exit(1);}
console.log('done');}
main().catch(e=>{console.error(e);process.exit(1);});
