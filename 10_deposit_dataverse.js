import fs from 'node:fs';
import path from 'node:path';
import {Checkpoint,ensureDir,saveJsonAtomic,loadJson,sleep} from './lib/util.js';
import {STATE_DIR} from './config.js';
const RELEASE=process.env.RELEASE_DIR||'release';
const SERVER=(process.env.DATAVERSE_URL||'https://dataverse.harvard.edu').replace(/\/+$/,'');
const TOKEN=process.env.DATAVERSE_TOKEN||'';
const PARENT=process.env.DATAVERSE_PARENT||'';
const PUBLISH=process.env.PUBLISH||'';
const DRY=process.env.DRY_RUN==='1';
const TIMEOUT=Number(process.env.UPLOAD_TIMEOUT_MS||'3600000');
function auth(extra){return TOKEN?{'X-Dataverse-key':TOKEN,...extra}:{...extra};}
async function api(method,url,opts={}){const retries=opts.retries??5;let attempt=0;
for(;;){const ctrl=new AbortController();const to=setTimeout(()=>ctrl.abort(),opts.timeout||TIMEOUT);
try{const res=await fetch(url,{method,headers:auth(opts.headers||{}),body:opts.body,signal:ctrl.signal});clearTimeout(to);
const text=await res.text();let json=null;try{json=JSON.parse(text);}catch{}
if(res.status===429||res.status>=500){attempt++;if(attempt>retries)throw new Error(`HTTP ${res.status} ${url} ${text.slice(0,300)}`);await sleep(Math.min(60000,1000*2**attempt));continue;}
if(!res.ok)throw new Error(`HTTP ${res.status} ${url} ${text.slice(0,500)}`);
return json??{};}
catch(e){clearTimeout(to);if(/^HTTP \d+/.test(String(e.message)))throw e;attempt++;if(attempt>retries)throw e;await sleep(Math.min(60000,1000*2**attempt));}}}
async function fileBlob(p){if(fs.openAsBlob)return await fs.openAsBlob(p);return new Blob([fs.readFileSync(p)]);}
async function fixityAlgorithm(){try{const r=await api('GET',`${SERVER}/api/files/fixityAlgorithm`,{retries:1,timeout:30000});const v=r?.data?.message||r?.data||r?.message;const s=String(v||'').toUpperCase();if(s.includes('SHA-256')||s.includes('SHA256'))return'sha256';if(s.includes('SHA-1')||s.includes('SHA1'))return'sha1';if(s.includes('MD5'))return'md5';}catch{}return null;}
async function listDraftFiles(doi){try{const r=await api('GET',`${SERVER}/api/datasets/:persistentId/versions/:draft/files?persistentId=${encodeURIComponent(doi)}`,{retries:2,timeout:120000});const arr=r?.data||[];const m=new Map();
for(const fm of arr){const label=fm.label||fm.dataFile?.filename;const dir=fm.directoryLabel?fm.directoryLabel+'/':'';const ck=fm.dataFile?.checksum||{};m.set(dir+label,{id:fm.dataFile?.id,label,checksumType:String(ck.type||'').toUpperCase().replace('-',''),checksumValue:String(ck.value||'').toLowerCase()});}
return m;}catch(e){console.log('could not list existing draft files (treating dataset as empty):',String(e.message||e).slice(0,200));return new Map();}}
async function createDataset(){const meta=path.join(RELEASE,'dataverse_dataset.json');
if(!fs.existsSync(meta))throw new Error('missing '+meta+': run 09_package_release.js first');
if(!PARENT)throw new Error('set DATAVERSE_PARENT to the alias of the collection to deposit into (e.g. your personal collection alias), or set DATAVERSE_DOI to reuse an existing dataset');
const body=fs.readFileSync(meta,'utf8');
if(DRY){console.log('[dry-run] would create a dataset in collection',PARENT,'on',SERVER);return'doi:DRY/RUN';}
const r=await api('POST',`${SERVER}/api/dataverses/${encodeURIComponent(PARENT)}/datasets`,{headers:{'Content-Type':'application/json'},body,retries:2,timeout:120000});
const d=r?.data||{};const doi=d.persistentId||(d.protocol&&d.authority&&d.identifier?`${d.protocol}:${d.authority}/${d.identifier}`:null);
if(!doi)throw new Error('dataset created but no persistent identifier returned: '+JSON.stringify(r).slice(0,300));
console.log('created dataset',doi);return doi;}
async function addFile(doi,entry,file){const fd=new FormData();
fd.append('file',await fileBlob(file),entry.name);
fd.append('jsonData',JSON.stringify({description:entry.description||'',categories:entry.categories||['Data'],restrict:'false',tabIngest:'false'}));
const r=await api('POST',`${SERVER}/api/datasets/:persistentId/add?persistentId=${encodeURIComponent(doi)}`,{body:fd,retries:3});
const f=r?.data?.files?.[0]?.dataFile;return f?f.id:null;}
async function replaceFile(id,entry,file){const fd=new FormData();
fd.append('file',await fileBlob(file),entry.name);
fd.append('jsonData',JSON.stringify({description:entry.description||'',categories:entry.categories||['Data'],forceReplace:true,tabIngest:'false'}));
const r=await api('POST',`${SERVER}/api/files/${id}/replace`,{body:fd,retries:3});
const f=r?.data?.files?.[0]?.dataFile;return f?f.id:id;}
async function main(){
const manifestPath=path.join(RELEASE,'manifest.json');
if(!fs.existsSync(manifestPath)){console.error('missing '+manifestPath+': run 09_package_release.js first');process.exit(1);}
if(!TOKEN&&!DRY){console.error('set DATAVERSE_TOKEN (create one under your Dataverse account: API Token tab). Use DRY_RUN=1 to preview without a token.');process.exit(1);}
const manifest=loadJson(manifestPath,null);
const cp=new Checkpoint(path.join(STATE_DIR,'dataverse.json'),{server:SERVER,doi:process.env.DATAVERSE_DOI||null,uploaded:{}});
if(process.env.DATAVERSE_DOI)cp.state.doi=process.env.DATAVERSE_DOI;
if(!cp.state.doi){cp.state.doi=await createDataset();cp.save();}
const doi=cp.state.doi;
console.log('depositing',manifest.files.length,'files to',doi,'on',SERVER,DRY?'[dry-run]':'');
const algo=DRY?null:await fixityAlgorithm();
if(algo)console.log('server fixity algorithm:',algo);
const existing=DRY?new Map():await listDraftFiles(doi);
let added=0,replaced=0,skipped=0;
for(const entry of manifest.files){const file=path.join(RELEASE,entry.name);
if(!fs.existsSync(file)){console.log('missing locally, skipping:',entry.name);continue;}
const prior=cp.state.uploaded[entry.name];
if(prior&&prior.sha256===entry.sha256&&existing.has(entry.name)){skipped++;continue;}
const remote=existing.get(entry.name);
if(remote&&algo&&remote.checksumValue&&remote.checksumValue===entry[algo]){cp.state.uploaded[entry.name]={id:remote.id,sha256:entry.sha256,at:new Date().toISOString()};cp.save();skipped++;continue;}
const mb=(entry.bytes/1048576).toFixed(1);
if(DRY){console.log(`[dry-run] would ${remote?'replace':'upload'} ${entry.name} (${mb} MB)`);remote?replaced++:added++;continue;}
try{const t0=Date.now();
const id=remote?await replaceFile(remote.id,entry,file):await addFile(doi,entry,file);
cp.state.uploaded[entry.name]={id,sha256:entry.sha256,at:new Date().toISOString()};cp.save();
console.log(`${remote?'replaced':'uploaded'} ${entry.name} (${mb} MB in ${((Date.now()-t0)/1000).toFixed(1)}s)`);
remote?replaced++:added++;}
catch(e){const msg=String(e.message||e);console.error('FAILED',entry.name,'-',msg.slice(0,400));
if(/exceeds|too large|quota/i.test(msg))console.error('  hint: this installation caps file size (Harvard Dataverse is 2.5 GB); re-run 09 with a lower MAX_FILE_MB to split it');
cp.state.lastError={file:entry.name,error:msg,at:new Date().toISOString()};cp.save();}
await sleep(500);}
ensureDir('reports');
saveJsonAtomic(path.join('reports','dataverse_deposit.json'),{server:SERVER,doi,landing_page:`${SERVER}/dataset.xhtml?persistentId=${doi}`,deposited_at:new Date().toISOString(),published:false,files:cp.state.uploaded,manifest_generated_at:manifest.generated_at});
console.log(`done: ${added} uploaded, ${replaced} replaced, ${skipped} already current`);
console.log('draft:',`${SERVER}/dataset.xhtml?persistentId=${doi}`);
if(PUBLISH&&!DRY){if(!['major','minor'].includes(PUBLISH)){console.error("PUBLISH must be 'major' or 'minor'");process.exit(1);}
console.log('publishing as a',PUBLISH,'version (this is irreversible: published versions cannot be deleted)');
const r=await api('POST',`${SERVER}/api/datasets/:persistentId/actions/:publish?persistentId=${encodeURIComponent(doi)}&type=${PUBLISH}`,{retries:2,timeout:600000});
const v=r?.data||{};console.log('published version',[v.versionNumber,v.versionMinorNumber].filter(x=>x!=null).join('.')||'(pending)');
saveJsonAtomic(path.join('reports','dataverse_deposit.json'),{server:SERVER,doi,landing_page:`${SERVER}/dataset.xhtml?persistentId=${doi}`,deposited_at:new Date().toISOString(),published:true,publish_type:PUBLISH,files:cp.state.uploaded,manifest_generated_at:manifest.generated_at});}
else if(!DRY)console.log('not published: review the draft in the browser, then re-run with PUBLISH=major');}
main().catch(e=>{console.error(e);process.exit(1);});
