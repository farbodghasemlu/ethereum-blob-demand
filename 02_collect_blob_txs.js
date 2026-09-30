import path from 'node:path';
import {BLOBSCAN_API,DENCUN_BLOCK,DATA_DIR,STATE_DIR,RPC_URLS} from './config.js';
import {Checkpoint,NdjsonWriter,fetchWithRetry,sleep} from './lib/util.js';
const W=Number(process.env.WINDOW||'10000');
const PS=Number(process.env.PAGE_SIZE||'100');
const RATE=Number(process.env.RATE_MS||'120');
const CONC=Number(process.env.PAGE_CONCURRENCY||'4');
async function latestBlock(){try{const r=await fetchWithRetry(`${BLOBSCAN_API}/blocks?p=1&ps=1&sort=desc`);const arr=r.blocks||r.items||(Array.isArray(r)?r:null);if(arr&&arr[0]&&arr[0].number!=null)return Number(arr[0].number);}catch{}
const r=await fetchWithRetry(RPC_URLS[0],{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'eth_blockNumber',params:[]})});return Number(BigInt(r.result));}
async function fetchPage(s,e,p,expand){const q=`startBlock=${s}&endBlock=${e}&sort=asc&ps=${PS}&p=${p}`+(expand?'&expand=blob':'');const r=await fetchWithRetry(`${BLOBSCAN_API}/transactions?${q}`,{},{retries:10,timeout:120000});return r.transactions||r.items||(Array.isArray(r)?r:[]);}
async function main(){const cp=new Checkpoint(path.join(STATE_DIR,'blobscan_txs.json'),{windowStart:Number(process.env.START_BLOCK||DENCUN_BLOCK),page:1,expand:true});const latest=Number(process.env.END_BLOCK||await latestBlock());console.log('collecting blobscan txs from block',cp.state.windowStart,'to',latest);
while(cp.state.windowStart<=latest){const s=cp.state.windowStart;const e=Math.min(s+W-1,latest);const w=new NdjsonWriter(path.join(DATA_DIR,'raw','blobscan_txs','txs_'+String(s).padStart(10,'0')+'.ndjson'));let p=cp.state.page;let total=0;
let done=false;const wt0=Date.now();
while(!done){const pages=[];for(let i=0;i<CONC;i++)pages.push(p+i);let lists;try{lists=await Promise.all(pages.map(pp=>fetchPage(s,e,pp,cp.state.expand)));}catch(err){if(cp.state.expand&&/^HTTP 4\d\d/.test(String(err.message||err))){console.log('expand=blob rejected, retrying without expand');cp.state.expand=false;cp.save();continue;}throw err;}
for(const list of lists){for(const t of list)w.write(t);total+=list.length;if(list.length<PS){done=true;break;}}
p+=CONC;if(!done){cp.state.page=p;cp.save();}
const rate=(total/Math.max((Date.now()-wt0)/1000,0.001)).toFixed(0);if(process.stdout.isTTY)process.stdout.write(`  [${s}-${e}] page ${p-1} | ${total} txs | ${rate} tx/s          \r`);else if(Math.floor((p-1)/CONC)%10===0)console.log(`  [${s}-${e}] page ${p-1} | ${total} txs | ${rate} tx/s`);if(!done)await sleep(RATE);}
w.close();if(process.stdout.isTTY)process.stdout.write(' '.repeat(90)+'\r');console.log('window',s,'-',e,':',total,'txs in',((Date.now()-wt0)/1000).toFixed(0)+'s');
cp.state.windowStart=e+1;cp.state.page=1;cp.save();await sleep(RATE);}
console.log('done');}
main().catch(e=>{console.error(e);process.exit(1);});
