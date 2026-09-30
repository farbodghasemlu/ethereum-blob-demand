import {loadJson} from './lib/util.js';
export const DATA_DIR='data';
export const STATE_DIR='state';
export const OUT_DIR='datasets';
export const RPC_URLS=process.env.RPC_URLS?process.env.RPC_URLS.split(','):['https://ethereum-rpc.publicnode.com','https://eth.drpc.org','https://rpc.flashbots.net','https://eth.llamarpc.com','https://1rpc.io/eth'];
export const DENCUN_BLOCK=19426587;
export const BLOB_GAS_PER_BLOB=131072;
// Blob schedule verified block by block against the excess-blob-gas update rule (forks/pin_forks.js,
// forks/detect_7918.js, analysis/01_data_audit.py). forks.json, if present, overrides it.
const DEFAULT_FORKS=[{name:'dencun',ts:1710338135,target:3,max:6,updateFraction:3338477},{name:'pectra',ts:1746612311,target:6,max:9,updateFraction:5007716},{name:'fusaka',ts:1764798551,target:6,max:9,updateFraction:5007716},{name:'bpo1',ts:1765290071,target:10,max:15,updateFraction:8346193},{name:'bpo2',ts:1767747671,target:14,max:21,updateFraction:11684671}];
export const FORKS=loadJson('forks.json',DEFAULT_FORKS);
export const BUILTIN_ROLLUP_MAP={'0x5050f69a9786f081509234f1a7f4684b5e5b76c9':'base','0x6887246668a3b87f54deb3b94ba47a6f63f32985':'optimism','0xc1b634853cb333d3ad8663715b08f41a3aec47cc':'arbitrum','0xcf2898225ed05be911d3709d9417e86e0b4cfc8f':'scroll','0xa9268341831efa4937537bc3e9eb36dbece83c7e':'linea','0x0d3250c3d5facb74ac15834096397a3ef790ec99':'zksync','0x415c8893d514f9bc5211d36eeda4183226b84aa7':'blast','0x000000633b68f5d8d3a86593ebb815b4663bcbe0':'taiko','0x2c169dfe5fbba12957bdd0ba47d9cedbfe260ca7':'starknet','0x99199a22125034c808ff20f377d91187e8050f2e':'mode','0x625726c858dbf78c0125436c943bf4b4be9d9033':'zora','0xe1b64045351b0b6e9821f19b39f81bc4711d2230':'boba'};
export const BLOBSCAN_API=process.env.BLOBSCAN_API||'https://api.blobscan.com';
export const CELENIUM_API=process.env.CELENIUM_API||'https://api-mainnet.celenium.io/v1';
export const GROWTHEPIE_API=process.env.GROWTHEPIE_API||'https://api.growthepie.com/v1';
export const GROWTHEPIE_EXPORTS=(process.env.GROWTHEPIE_EXPORTS||'txcount,daa,fees,rent_paid,throughput,txcosts,blob_size,costs_blobs,costs_l1,costs,profit,tvl,stables_mcap,market_cap,fdv,app_revenue').split(',');
export const BINANCE_API=process.env.BINANCE_API||'https://api.binance.com';
export const COINBASE_API=process.env.COINBASE_API||'https://api.exchange.coinbase.com';
export const XATU_BASE=process.env.XATU_BASE||'https://data.ethpandaops.io/xatu/mainnet/databases/default';
export const ROLLUP_ADDRESS_MAP=Object.fromEntries(Object.entries({...BUILTIN_ROLLUP_MAP,...loadJson(process.env.ROLLUP_MAP_FILE||'rollups.json',{})}).map(([k,v])=>[k.toLowerCase(),v]));
