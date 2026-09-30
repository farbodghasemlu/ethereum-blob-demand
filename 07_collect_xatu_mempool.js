import fs from 'node:fs';
import path from 'node:path';
import {XATU_BASE,DATA_DIR,STATE_DIR} from './config.js';
import {Checkpoint,ensureDir} from './lib/util.js';
import {openDuck} from './lib/duck.js';
const TABLE=process.env.XATU_TABLE||'mempool_transaction';
const START=process.env.XATU_START||'2024-03-13';
const END=process.env.XATU_END||new Date(Date.now()-2*86400000).toISOString().slice(0,10);
function*dates(a,b){let d=new Date(a+'T00:00:00Z');const e=new Date(b+'T00:00:00Z');while(d<=e){yield d.toISOString().slice(0,10);d=new Date(d.getTime()+86400000);}}
async function main(){ensureDir(path.join(DATA_DIR,'raw','xatu_mempool'));const cp=new Checkpoint(path.join(STATE_DIR,'xatu.json'),{done:{}});for(const[k,v]of Object.entries(cp.state.done))if(v==='fail')delete cp.state.done[k];
const{all,run,close}=openDuck(':memory:');
try{await run('INSTALL httpfs');await run('LOAD httpfs');}catch(e){console.log('httpfs load issue (may already be loaded):',String(e.message||e));}
// One DuckDB instance serves every day; without a cap its buffer/HTTP caches grew to 25 GB on 1.6 GB daily files.
await run(`SET memory_limit='${process.env.DUCKDB_MEMORY_LIMIT||'4GB'}'`);try{await run('SET enable_external_file_cache=false');}catch{}try{await run('SET enable_http_metadata_cache=false');}catch{}
const describeUrl=async u=>{try{return await all(`DESCRIBE SELECT * FROM read_parquet('${u}')`);}catch{return null;}};
for(const date of dates(START,END)){if(cp.state.done[date]){continue;}
const[y,m,d]=date.split('-');const mu=String(Number(m));const du=String(Number(d));
let urls=[];let descr=null;
for(const u of[`${XATU_BASE}/${TABLE}/${y}/${mu}/${du}.parquet`,`${XATU_BASE}/${TABLE}/${y}/${m}/${d}.parquet`]){descr=await describeUrl(u);if(descr){urls=[u];break;}}
if(!descr){for(let h=0;h<24;h++){for(const u of[`${XATU_BASE}/${TABLE}/${y}/${mu}/${du}/${h}.parquet`,`${XATU_BASE}/${TABLE}/${y}/${m}/${d}/${h}.parquet`]){const dd=await describeUrl(u);if(dd){urls.push(u);if(!descr)descr=dd;break;}}}}
if(!descr||urls.length===0){console.log(date,'no parquet found, skipping');cp.state.done[date]='skip:not_found';cp.save();continue;}
const cols=descr.map(r=>r.column_name);
const typeCol=['type','transaction_type','tx_type'].find(c=>cols.includes(c));
const hashCol=['hash','transaction_hash'].find(c=>cols.includes(c));
const timeCol=['event_date_time','event_datetime','seen_at','updated_date_time'].find(c=>cols.includes(c));
if(!typeCol||!hashCol){console.log(date,'required columns missing, skipping');cp.state.done[date]='skip:schema';cp.save();continue;}
// Xatu stores hashes/addresses/fee caps as BLOBs holding ASCII hex: decode to VARCHAR or they never join to blob_txs.hash.
// One row per tx (not per sensor sighting): first_seen = earliest observation across the sensor fleet that day.
const types=Object.fromEntries(descr.map(r=>[r.column_name,r.column_type]));
// Fee caps are ClickHouse UInt128 exported as 16-byte little-endian BLOBs: keep them as hex (decode downstream if needed).
const LE_UINT=new Set(['gas_price','gas_fee_cap','gas_tip_cap','blob_gas_fee_cap','max_fee_per_blob_gas','value']);
const str=c=>types[c]!=='BLOB'?`CAST("${c}" AS VARCHAR)`:LE_UINT.has(c)?`hex("${c}")`:`decode("${c}")`;
const sensorCol=['meta_client_name','meta_client_id'].find(c=>cols.includes(c));
const extras=['from','nonce','gas_fee_cap','gas_tip_cap','blob_gas_fee_cap','max_fee_per_blob_gas','blob_gas'].filter(c=>cols.includes(c));
const sel=[`lower(${str(hashCol)}) AS hash`,timeCol?`min("${timeCol}") AS seen_at`:'NULL AS seen_at','count(*) AS n_obs',
 sensorCol?`count(DISTINCT "${sensorCol}") AS n_sensors`:'NULL AS n_sensors',...extras.map(c=>`any_value(${str(c)}) AS "${c}"`)].join(',');
const srcs=urls.map(u=>`'${u}'`).join(',');
const out=path.join(DATA_DIR,'raw','xatu_mempool',date+'.csv');
try{await run(`COPY (SELECT ${sel} FROM read_parquet([${srcs}],union_by_name=true) WHERE TRY_CAST("${typeCol}" AS INTEGER)=3 GROUP BY 1) TO '${out.replaceAll("'","''")}' (FORMAT CSV, HEADER)`);cp.state.done[date]='ok';console.log(date,'ok',urls.length,'file(s)');}catch(e){console.log(date,'failed:',String(e.message||e));delete cp.state.done[date];(cp.state.failed??={})[date]=String(e.message||e).slice(0,200);}
cp.save();}
await close();console.log('done (this source is experimental; missing days are recorded in state/xatu.json and do not block the pipeline)');}
main().catch(e=>{console.error(e);process.exit(1);});
