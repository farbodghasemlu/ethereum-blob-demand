import path from 'node:path';
import {BLOBSCAN_API,DATA_DIR} from './config.js';
import {fetchWithRetry,saveJsonAtomic,sleep} from './lib/util.js';
const PROBES=[['overall','/stats/overall'],['stats_root','/stats'],['blocks_all','/stats/blocks?timeFrame=All'],['transactions_all','/stats/transactions?timeFrame=All'],['blobs_all','/stats/blobs?timeFrame=All'],['blocks_180d','/stats/blocks?timeFrame=180d'],['transactions_180d','/stats/transactions?timeFrame=180d'],['blobs_180d','/stats/blobs?timeFrame=180d']];
async function main(){let ok=0;for(const[key,p]of PROBES){try{const r=await fetchWithRetry(`${BLOBSCAN_API}${p}`,{},{retries:4});saveJsonAtomic(path.join(DATA_DIR,'raw','blobscan_stats',key+'.json'),{fetched_at:new Date().toISOString(),endpoint:p,data:r});console.log('ok',key);ok++;}catch(e){console.log('skip',key,String(e.message||e));}await sleep(300);}
console.log('done,',ok,'of',PROBES.length,'endpoints saved (failures are non-fatal; these files are for cross-validation only)');}
main().catch(e=>{console.error(e);process.exit(1);});
