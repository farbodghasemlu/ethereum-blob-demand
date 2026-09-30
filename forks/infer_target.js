import {openDuck} from '../lib/duck.js';
import {FORKS} from '../config.js';
const {all,close}=openDuck(':memory:');
const B="'datasets/blocks_panel.parquet'";
const show=(t,r)=>{console.log('\n### '+t);console.table(r.map(x=>Object.fromEntries(Object.entries(x).map(([k,v])=>[k,typeof v==='bigint'?v.toString():v]))));};
try{
await all(`CREATE OR REPLACE TABLE seq AS SELECT number,timestamp,blob_gas_used,excess_blob_gas,lead(excess_blob_gas) OVER (ORDER BY number) AS next_excess,lead(number) OVER (ORDER BY number) AS next_number FROM ${B}`);
await all(`CREATE OR REPLACE TABLE implied AS SELECT number,timestamp,CAST(to_timestamp(timestamp) AS DATE) AS date,(CAST(excess_blob_gas AS BIGINT)+CAST(blob_gas_used AS BIGINT)-CAST(next_excess AS BIGINT))/131072.0 AS implied_target FROM seq WHERE next_number=number+1 AND next_excess>0`);
show('implied blob target per regime (from the EIP-4844 excess update rule; should equal the configured target exactly)',await all(`
SELECT f.name AS regime,f.target_blobs AS configured,mode(i.implied_target) AS implied_mode,count(*) AS blocks_usable,round(100.0*sum(CASE WHEN i.implied_target=f.target_blobs THEN 1 ELSE 0 END)/count(*),3) AS pct_agreeing
FROM implied i ASOF JOIN (SELECT name,ts,target_blobs FROM (SELECT * FROM (VALUES ${FORKS.map(f=>`('${f.name}',${f.ts},${f.target})`).join(',')}) t(name,ts,target_blobs))) f ON i.timestamp>=f.ts
GROUP BY f.name,f.target_blobs ORDER BY min(i.timestamp)`));
show('exact block where the implied target changes (empirical fork activation)',await all(`
SELECT implied_target AS new_target,min(number) AS first_block,min(timestamp) AS ts,CAST(to_timestamp(min(timestamp)) AS VARCHAR) AS utc
FROM (SELECT *,lag(implied_target) OVER (ORDER BY number) AS prev FROM implied) WHERE prev IS NOT NULL AND implied_target<>prev
GROUP BY implied_target HAVING count(*)>50 ORDER BY min(timestamp)`));
}catch(e){console.error('failed:',String(e.message||e));}
await close();
