import fs from 'node:fs';
import path from 'node:path';
import {BINANCE_API,COINBASE_API,DATA_DIR} from './config.js';
import {CsvWriter,fetchWithRetry,sleep} from './lib/util.js';
const START=Date.parse(process.env.PRICE_START||'2023-10-01T00:00:00Z');
async function binance(symbol){const rows=[];let start=START;for(;;){const r=await fetchWithRetry(`${BINANCE_API}/api/v3/klines?symbol=${symbol}&interval=1d&startTime=${start}&limit=1000`,{},{retries:4});if(!Array.isArray(r)||r.length===0)break;for(const k of r)rows.push([new Date(k[0]).toISOString().slice(0,10),k[1],k[2],k[3],k[4],k[5],'binance']);start=r[r.length-1][6]+1;if(r.length<1000)break;await sleep(300);}return rows;}
async function coinbase(product){const rows=[];let s=START;const now=Date.now();while(s<now){const e=Math.min(s+300*86400000,now);const url=`${COINBASE_API}/products/${product}/candles?granularity=86400&start=${new Date(s).toISOString()}&end=${new Date(e).toISOString()}`;let r;try{r=await fetchWithRetry(url,{headers:{'user-agent':'blob-da-market-pipeline'}},{retries:4});}catch(err){console.log(product,'coinbase window failed',String(err.message||err));r=[];}
if(Array.isArray(r))for(const c of r)rows.push([new Date(c[0]*1000).toISOString().slice(0,10),c[3],c[2],c[1],c[4],c[5],'coinbase']);s=e+86400000;await sleep(350);}return rows;}
async function collect(asset,binSym,cbProd){let rows=[];try{rows=await binance(binSym);}catch(e){console.log(asset,'binance failed:',String(e.message||e));}
if(rows.length===0){console.log(asset,'falling back to coinbase');rows=await coinbase(cbProd);}
const byDate=new Map();for(const r of rows)byDate.set(r[0],r);const sorted=[...byDate.values()].sort((a,b)=>a[0]<b[0]?-1:1);
const file=path.join(DATA_DIR,'raw','prices',asset+'_daily.csv');fs.mkdirSync(path.dirname(file),{recursive:true});fs.rmSync(file,{force:true});
const w=new CsvWriter(file,['date','open','high','low','close','volume','source']);for(const r of sorted)w.writeRow(r);w.close();console.log(asset,':',sorted.length,'days');}
async function main(){await collect('ETH','ETHUSDT','ETH-USD');await collect('TIA','TIAUSDT','TIA-USD');console.log('done');}
main().catch(e=>{console.error(e);process.exit(1);});
