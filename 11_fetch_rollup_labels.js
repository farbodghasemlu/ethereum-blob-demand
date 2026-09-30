import fs from 'node:fs';
import {fetchWithRetry,saveJsonAtomic,loadJson} from './lib/util.js';
const URL=process.env.BLOBLIST_URL||'https://github.com/tirante-dev/blob-list/releases/latest/download/eip155-1.json';
const OUT=process.env.ROLLUP_MAP_FILE||'rollups.json';
async function main(){console.log('fetching blob-list attribution registry');
const r=await fetchWithRetry(URL,{headers:{'user-agent':'blob-da-market-pipeline/1.0 research','accept':'application/json'}},{retries:5,timeout:120000});
const addrs=r&&r.addresses;
if(!addrs||typeof addrs!=='object'){console.error('unexpected registry shape; nothing written');process.exit(1);}
const existing=loadJson(OUT,{});
const merged={...existing};let added=0,total=0;
for(const[addr,claims]of Object.entries(addrs)){if(!Array.isArray(claims)||claims.length===0)continue;
const c=claims.find(x=>x&&x.entity_id)||claims[0];if(!c||!c.entity_id)continue;
const key=addr.toLowerCase();total++;
if(!merged[key]){added++;}
merged[key]=c.entity_id;}
saveJsonAtomic(OUT,Object.fromEntries(Object.entries(merged).sort()));
const byEntity=new Map();for(const v of Object.values(merged))byEntity.set(v,(byEntity.get(v)||0)+1);
console.log(`registry supplied ${total} addresses; ${added} new; ${Object.keys(merged).length} total in ${OUT} covering ${byEntity.size} entities`);
console.log('rerun "npm run merge" to apply the new labels (no recollection needed)');}
main().catch(e=>{console.error(e);process.exit(1);});
