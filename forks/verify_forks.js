import {openDuck} from '../lib/duck.js';
import {FORKS} from '../config.js';
const {all,close}=openDuck(':memory:');
const B="'datasets/blocks_panel.parquet'";
const T="'datasets/blob_txs.parquet'";
const p=(t,r)=>{console.log('\n### '+t);console.table(r.map(x=>Object.fromEntries(Object.entries(x).map(([k,v])=>[k,typeof v==='bigint'?v.toString():v]))));};
const ts=s=>`to_timestamp(${s})`;
try{
p('empirical fork activations (first block exceeding each regime cap)',await all(`
SELECT 'first >6 blobs (pectra)' AS event,min(number) AS block,min(timestamp) AS ts,CAST(${ts('min(timestamp)')} AS VARCHAR) AS utc FROM ${B} WHERE blob_count>6
UNION ALL SELECT 'first >9 blobs (bpo1)',min(number),min(timestamp),CAST(${ts('min(timestamp)')} AS VARCHAR) FROM ${B} WHERE blob_count>9
UNION ALL SELECT 'first >15 blobs (bpo2)',min(number),min(timestamp),CAST(${ts('min(timestamp)')} AS VARCHAR) FROM ${B} WHERE blob_count>15`));
p('last block at the 1-wei fee floor (EIP-7918 should end this at Fusaka)',await all(`
SELECT max(number) AS last_at_floor_block,max(timestamp) AS ts,CAST(${ts('max(timestamp)')} AS VARCHAR) AS utc FROM ${B} WHERE at_floor`));
p('configured fork timestamps for comparison',FORKS.map(f=>({regime:f.name,ts:f.ts,utc:new Date(f.ts*1000).toISOString(),target:f.target,max:f.max})));
p('top unattributed batchers (add these to ROLLUP_ADDRESS_MAP)',await all(`
SELECT from_address,count(*) AS txs,sum(blob_count) AS blobs,CAST(min(date) AS VARCHAR) AS first_seen,CAST(max(date) AS VARCHAR) AS last_seen
FROM ${T} WHERE rollup='unknown' AND from_address IS NOT NULL GROUP BY 1 ORDER BY blobs DESC LIMIT 20`));
p('share of blob demand still unattributed, by year',await all(`
SELECT year(date) AS yr,round(100.0*sum(CASE WHEN rollup='unknown' THEN blob_count ELSE 0 END)/sum(blob_count),2) AS pct_blobs_unknown FROM ${T} GROUP BY 1 ORDER BY 1`));
p('blob txs with no matching header (top up script 01 if nonzero)',await all(`
SELECT count(*) AS orphan_txs,min(block_number) AS first_block,max(block_number) AS last_block FROM ${T} WHERE block_ts IS NULL`));
}catch(e){console.error('query failed:',String(e.message||e));}
await close();
