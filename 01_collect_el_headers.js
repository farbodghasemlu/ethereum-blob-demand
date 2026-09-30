import path from 'node:path';
import {RPC_URLS,DENCUN_BLOCK,DATA_DIR,STATE_DIR} from './config.js';
import {Checkpoint,CsvWriter,fetchWithRetry,sleep} from './lib/util.js';
const BATCH=Number(process.env.BATCH||'20');
const CONC=Number(process.env.CONCURRENCY||'4');
const STRIDE=Number(process.env.STRIDE||'1');
const SHARD=50000;
const HEADER=['number','timestamp','hash','parent_hash','fee_recipient','gas_limit','gas_used','base_fee_per_gas','blob_gas_used','excess_blob_gas','tx_count','size_bytes'];
let rpcIdx=0;
async function rpcCall(body){let lastErr;for(let a=0;a<RPC_URLS.length*4;a++){const url=RPC_URLS[rpcIdx%RPC_URLS.length];try{const r=await fetchWithRetry(url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)},{retries:2,timeout:60000});if(Array.isArray(body)){if(!Array.isArray(r))throw new Error('batch unsupported');return r;}if(r&&r.error)throw new Error(JSON.stringify(r.error));return r;}catch(e){lastErr=e;rpcIdx++;await sleep(500);}}throw lastErr;}
async function getBlock(n){const r=await rpcCall({jsonrpc:'2.0',id:1,method:'eth_getBlockByNumber',params:['0x'+n.toString(16),false]});if(!r||!r.result)throw new Error('null block '+n);return r.result;}
async function getBatch(nums){let byId=new Map();try{const body=nums.map(n=>({jsonrpc:'2.0',id:n,method:'eth_getBlockByNumber',params:['0x'+n.toString(16),false]}));const rs=await rpcCall(body);for(const r of rs){if(r&&r.result)byId.set(Number(r.id),r.result);}}catch(e){byId=new Map();}
const out=[];for(const n of nums){let b=byId.get(n)||null;for(let t=0;t<6&&!b;t++){try{b=await getBlock(n);}catch{await sleep(800);}}if(!b)throw new Error('failed to fetch block '+n+' from all RPCs');out.push(b);}return out;}
function row(b){const n=Number(BigInt(b.number));return[n,Number(BigInt(b.timestamp)),b.hash,b.parentHash,(b.miner||'').toLowerCase(),Number(BigInt(b.gasLimit)),Number(BigInt(b.gasUsed)),BigInt(b.baseFeePerGas||'0x0').toString(),b.blobGasUsed!=null?Number(BigInt(b.blobGasUsed)):0,b.excessBlobGas!=null?BigInt(b.excessBlobGas).toString():'0',Array.isArray(b.transactions)?b.transactions.length:0,b.size!=null?Number(BigInt(b.size)):''];}
async function main(){const startEnv=Number(process.env.START_BLOCK||DENCUN_BLOCK);const cp=new Checkpoint(path.join(STATE_DIR,'el_headers.json'),{next:startEnv});let latest;if(process.env.END_BLOCK){latest=Number(process.env.END_BLOCK);}else{const r=await rpcCall({jsonrpc:'2.0',id:1,method:'eth_blockNumber',params:[]});latest=Number(BigInt(r.result));}
const cur={shard:-1,w:null};const writerFor=n=>{const s=Math.floor(n/SHARD)*SHARD;if(cur.shard!==s){if(cur.w)cur.w.close();cur.w=new CsvWriter(path.join(DATA_DIR,'raw','el_headers','headers_'+String(s).padStart(10,'0')+'.csv'),HEADER);cur.shard=s;}return cur.w;};
let done=0;const t0=Date.now();console.log('collecting headers from',cp.state.next,'to',latest,'stride',STRIDE);
while(cp.state.next<=latest){const groups=[];let n=cp.state.next;for(let g=0;g<CONC&&n<=latest;g++){const nums=[];for(let i=0;i<BATCH&&n<=latest;i++){nums.push(n);n+=STRIDE;}if(nums.length)groups.push(nums);}
const results=await Promise.all(groups.map(g=>getBatch(g)));for(const blocks of results){for(const b of blocks){const r=row(b);writerFor(r[0]).writeRow(r);}}
done+=groups.reduce((a,g)=>a+g.length,0);cp.state.next=n;cp.save();
if(done%2000<BATCH*CONC){const rate=done/((Date.now()-t0)/1000);const remain=(latest-cp.state.next+1)/STRIDE;console.log('at block',cp.state.next,'|',rate.toFixed(1),'blk/s | eta_h',(remain/Math.max(rate,0.001)/3600).toFixed(2));}}
if(cur.w)cur.w.close();console.log('done,',done,'blocks written this run');}
main().catch(e=>{console.error(e);process.exit(1);});
