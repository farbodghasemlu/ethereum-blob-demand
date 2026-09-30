import {openDuck} from '../lib/duck.js';
import {FORKS} from '../config.js';
const {all,close}=openDuck(':memory:');
const B=`'${process.env.PANEL||'datasets/blocks_panel.parquet'}'`;
const GENESIS=Number(process.env.BEACON_GENESIS||'1606824023');
const EPOCH=384;
const epochOf=ts=>Math.floor((ts-GENESIS)/EPOCH);
const epochStart=e=>GENESIS+e*EPOCH;
const iso=ts=>new Date(ts*1000).toISOString();
const S=131072;
async function bracket(prev,next){
const pT=prev.target,pM=prev.max,nT=next.target,nM=next.max;
const q=`WITH s AS (SELECT number,timestamp,blob_gas_used,blob_count,excess_blob_gas,lead(excess_blob_gas) OVER (ORDER BY number) AS nx,lead(timestamp) OVER (ORDER BY number) AS nts,lead(number) OVER (ORDER BY number) AS nn FROM ${B}),
e AS (SELECT number,nts,blob_count,CAST(nx AS BIGINT) AS nx,
greatest(0,CAST(excess_blob_gas AS BIGINT)+CAST(blob_gas_used AS BIGINT)-${pT*S}) AS sp,
greatest(0,CAST(excess_blob_gas AS BIGINT)+CAST(blob_gas_used AS BIGINT)-${nT*S}) AS sn,
CAST(excess_blob_gas AS BIGINT)+CAST(blob_gas_used AS BIGINT)*${pM-pT}/${pM} AS rp,
CAST(excess_blob_gas AS BIGINT)+CAST(blob_gas_used AS BIGINT)*${nM-nT}/${nM} AS rn
FROM s WHERE nn=number+1 AND nx>0)
SELECT max(CASE WHEN nx=sp AND nx<>sn AND nx<>rn THEN nts END) AS last_prev,
min(CASE WHEN nx=sn AND nx<>sp AND nx<>rp THEN nts END) AS first_next,
sum(CASE WHEN nx=sp AND nx<>sn AND nx<>rn THEN 1 ELSE 0 END) AS n_prev,
sum(CASE WHEN nx=sn AND nx<>sp AND nx<>rp THEN 1 ELSE 0 END) AS n_next FROM e`;
const r=(await all(q))[0];
return{last_prev:r.last_prev==null?null:Number(r.last_prev),first_next:r.first_next==null?null:Number(r.first_next),n_prev:Number(r.n_prev),n_next:Number(r.n_next)};}
async function main(){
const byName=Object.fromEntries(FORKS.map(f=>[f.name,f]));
const order=FORKS.slice().sort((a,b)=>a.ts-b.ts);
for(let i=1;i<order.length;i++){const prev=order[i-1],next=order[i];
if(prev.target===next.target&&prev.max===next.max){console.log(`\n### ${next.name}: blob parameters identical to ${prev.name}; not identifiable from the excess update rule`);continue;}
const b=await bracket(prev,next);
console.log(`\n### ${next.name}: configured ${next.ts} (${iso(next.ts)})`);
if(b.last_prev==null||b.first_next==null){console.log(`    insufficient unambiguous evidence (prev-only blocks: ${b.n_prev}, next-only blocks: ${b.n_next})`);continue;}
console.log(`    unambiguous blocks: ${b.n_prev} under target ${prev.target}, ${b.n_next} under target ${next.target}`);
console.log(`    last block governed by target ${prev.target}: ${b.last_prev} (${iso(b.last_prev)})`);
console.log(`    first block governed by target ${next.target}: ${b.first_next} (${iso(b.first_next)})`);
if(b.first_next<=b.last_prev){console.log('    inconsistent ordering; check the fork list or the panel');continue;}
const cands=[];for(let e=epochOf(b.last_prev)+1;e<=epochOf(b.first_next);e++){const t=epochStart(e);if(t>b.last_prev&&t<=b.first_next)cands.push(t);}
if(cands.length===0){console.log(`    NO epoch boundary in the bracket; activation is somewhere in (${b.last_prev}, ${b.first_next}]`);console.log(`    best point estimate: ${b.first_next} (${iso(b.first_next)})`);}
else{console.log(`    ${cands.length} admissible epoch boundary(ies): ${cands.map(c=>`${c} (${iso(c)})`).join(', ')}`);
const ok=cands.includes(next.ts);
console.log(`    configured value ${ok?'MATCHES':'does NOT match'}${ok?'':` -> set "${next.name}" ts to ${cands[cands.length-1]}`}`);}}
console.log('\nPut corrected values in forks.json, then: npm run merge && node forks/detect_7918.js');
await close();}
main().catch(async e=>{console.error('failed:',String(e.message||e));await close();});
