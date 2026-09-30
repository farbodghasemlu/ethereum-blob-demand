import {openDuck} from '../lib/duck.js';
import {FORKS} from '../config.js';
const {all,close}=openDuck(':memory:');
const B="'datasets/blocks_panel.parquet'";
const show=(t,r)=>{console.log('\n### '+t);console.table(r.map(x=>Object.fromEntries(Object.entries(x).map(([k,v])=>[k,typeof v==='bigint'?v.toString():v]))));};
const FORKVALS=FORKS.map(f=>`('${f.name}',${f.ts},${f.target},${f.max})`).join(',');
try{
await all(`CREATE OR REPLACE TABLE fk AS SELECT * FROM (VALUES ${FORKVALS}) t(name,ts,target_blobs,max_blobs)`);
await all(`CREATE OR REPLACE TABLE seq AS SELECT number,timestamp,base_fee_per_gas,blob_gas_used,blob_count,excess_blob_gas,lead(excess_blob_gas) OVER (ORDER BY number) AS next_excess,lead(number) OVER (ORDER BY number) AS next_number FROM ${B}`);
await all(`CREATE OR REPLACE TABLE cls AS SELECT s.number,s.timestamp,CAST(to_timestamp(s.timestamp) AS DATE) AS date,s.blob_count,s.base_fee_per_gas,s.excess_blob_gas,s.next_excess,f.name AS regime,f.target_blobs,f.max_blobs,
greatest(0,CAST(s.excess_blob_gas AS BIGINT)+CAST(s.blob_gas_used AS BIGINT)-f.target_blobs*131072) AS pred_standard,
CAST(s.excess_blob_gas AS BIGINT)+CAST(s.blob_gas_used AS BIGINT)*(f.max_blobs-f.target_blobs)/f.max_blobs AS pred_reserve
FROM seq s ASOF JOIN fk f ON s.timestamp>=f.ts WHERE s.next_number=s.number+1`);
await all(`CREATE OR REPLACE TABLE tagged AS SELECT *,(abs(next_excess-pred_standard)<=1) AS is_standard,(abs(next_excess-pred_reserve)<=1) AS is_reserve FROM cls`);
show('pricing rule in force, by regime (EIP-7918 reserve vs ordinary EIP-4844)',await all(`
SELECT regime,count(*) AS blocks,
round(100.0*sum(CASE WHEN is_standard THEN 1 ELSE 0 END)/count(*),2) AS pct_ordinary_4844,
round(100.0*sum(CASE WHEN is_reserve AND NOT is_standard THEN 1 ELSE 0 END)/count(*),2) AS pct_reserve_bound,
round(100.0*sum(CASE WHEN NOT is_standard AND NOT is_reserve THEN 1 ELSE 0 END)/count(*),2) AS pct_unexplained,
round(avg(blob_count),2) AS avg_blobs FROM tagged GROUP BY regime ORDER BY min(timestamp)`));
show('fork activation pinned from ordinary-rule blocks only (unambiguous target)',await all(`
SELECT target AS implied_target,min(number) AS first_block,min(timestamp) AS ts,CAST(to_timestamp(min(timestamp)) AS VARCHAR) AS utc,count(*) AS supporting_blocks FROM (
SELECT number,timestamp,(CAST(excess_blob_gas AS BIGINT)+blob_count*131072-CAST(next_excess AS BIGINT))/131072 AS target FROM tagged WHERE is_standard AND next_excess>0) 
WHERE target IN (3,6,10,14) GROUP BY target ORDER BY min(timestamp)`));
show('monthly share of blocks where the reserve price binds',await all(`
SELECT date_trunc('month',date) AS month,any_value(regime) AS regime,round(100.0*sum(CASE WHEN is_reserve AND NOT is_standard THEN 1 ELSE 0 END)/count(*),1) AS pct_reserve_bound,round(avg(base_fee_per_gas)/1e9,2) AS avg_exec_basefee_gwei
FROM tagged WHERE date>=DATE '2025-11-01' GROUP BY month ORDER BY month`));
}catch(e){console.error('failed:',String(e.message||e));}
await close();
