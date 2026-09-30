import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {openDuck} from './lib/duck.js';
import {OUT_DIR,FORKS} from './config.js';
import {ensureDir,saveJsonAtomic,loadJson} from './lib/util.js';
const RELEASE=process.env.RELEASE_DIR||'release';
const MAX_MB=Number(process.env.MAX_FILE_MB||'2048');
const INCLUDE_SOURCE=process.env.INCLUDE_SOURCE==='1';
const FILE_DOCS={'blocks_panel.parquet':{d:'Block-level panel of every Ethereum execution block from the Dencun fork onward, with EIP-4844 blob-fee state, fork regime, and derived boundary indicators. Primary supply-side dataset.',c:['Data']},'blocks_daily.parquet':{d:'Daily aggregation of the block panel: blob counts, utilization, and the share of blocks at the fee floor or at the blob cap.',c:['Data']},'blocks_daily.csv':{d:'CSV copy of blocks_daily.parquet.',c:['Data']},'fees_hourly.csv':{d:'Hourly aggregation of the block panel; used for high-frequency event studies around fork activations.',c:['Data']},'blob_txs.parquet':{d:'Transaction-level record of every blob-carrying (type-3) transaction: blobs purchased, bid cap, price paid, fee, and rollup attribution. Primary demand-side dataset.',c:['Data']},'blob_txs_sample.csv':{d:'First 50,000 rows of blob_txs.parquet in CSV form for inspection without a Parquet reader.',c:['Documentation','Data']},'rollup_daily.parquet':{d:'Rollup-by-day demand panel: posting frequency, batch size, DA spend in ETH and USD, and share of daily blob supply. Main estimation panel.',c:['Data']},'rollup_daily.csv':{d:'CSV copy of rollup_daily.parquet.',c:['Data']},'da_cross_daily.parquet':{d:'Daily cross-market panel comparing Ethereum blob DA against Celestia DA in quantity and cost terms, for extensive-margin and migration analysis.',c:['Data']},'da_cross_daily.csv':{d:'CSV copy of da_cross_daily.parquet.',c:['Data']},'prices_daily.csv':{d:'Daily ETH and TIA OHLCV series used to convert fees to USD.',c:['Data']},'celestia_rollup_daily.csv':{d:'Long-format per-rollup daily Celestia usage (bytes, blob count, fees).',c:['Data']},'growthepie_fundamentals.parquet':{d:'Long-format daily layer-2 fundamentals from growthepie, used to normalize data-availability demand by rollup activity.',c:['Data']},'mempool_inclusion.parquet':{d:'Blob transactions matched to their earliest public mempool observation, giving an inclusion delay for each. Used for the queueing analysis in the fee-floor regime.',c:['Data']},'validation_report.json':{d:'Machine-readable data-quality report produced by the merge step: row counts, duplicates removed, block gaps, per-regime statistics, null rates, cross-source reconciliation, and the fork configuration used.',c:['Documentation']},'README.md':{d:'Pipeline documentation: prerequisites, run order, environment variables, resumability, and fork-constant verification.',c:['Documentation']},'DATASETS.md':{d:'Full source and field-level documentation for every dataset in this deposit.',c:['Documentation']},'CODEBOOK.md':{d:'Generated codebook: every file, every column, with observed type, and row counts as deposited.',c:['Documentation']},'MANIFEST-SHA256.txt':{d:'SHA-256 checksums for every file in this deposit.',c:['Documentation']},'manifest.json':{d:'Machine-readable manifest: per-file size, SHA-256, MD5, SHA-1, row and column counts, and provenance.',c:['Documentation']},'pipeline-source.tar.gz':{d:'Source code of the collection and merge pipeline that generated these datasets.',c:['Code']}};
const TEMPLATE={title:'Ethereum Blob (EIP-4844) Data-Availability Market: Block, Transaction, and Rollup Panels',authors:[{name:'Lastname, Firstname',affiliation:'Your Institution',orcid:''}],contact:[{name:'Lastname, Firstname',affiliation:'Your Institution',email:'you@example.edu'}],description:'Analysis-ready panel datasets on the Ethereum data-availability (blob) market introduced by EIP-4844, spanning the Dencun, Pectra, and Fusaka blob-schedule regimes. Includes a block-level panel with blob fee state and boundary indicators, a transaction-level record of every blob-carrying transaction with prices and bid caps, a rollup-by-day demand panel, and a cross-market daily comparison with Celestia. Built entirely from free public APIs by the accompanying open-source pipeline.',subjects:['Social Sciences'],keywords:['Ethereum','EIP-4844','blob','data availability','rollups','transaction fees','market microstructure','blockchain'],kindOfData:['Observational data','Administrative records'],language:'English',depositor:'Lastname, Firstname',timePeriodStart:'2024-03-13',timePeriodEnd:'',license:'CC0 1.0',parentDataverse:'',relatedPublication:'',relatedMaterial:['Pipeline source code: https://github.com/USER/REPO','Data provided by Celenium API (https://celenium.io)','Layer-2 fundamentals from growthepie (https://growthepie.xyz), CC BY 4.0','Mempool observations from Xatu / ethPandaOps (https://ethpandaops.io), CC BY 4.0']};
function prim(name,value){return{typeName:name,multiple:false,typeClass:'primitive',value:String(value)};}
function primList(name,values){return{typeName:name,multiple:true,typeClass:'primitive',value:values.map(String)};}
function controlled(name,values){return{typeName:name,multiple:true,typeClass:'controlledVocabulary',value:values.map(String)};}
function compound(name,rows){return{typeName:name,multiple:true,typeClass:'compound',value:rows};}
function buildCitation(cfg){const fields=[];fields.push(prim('title',cfg.title));
fields.push(compound('author',cfg.authors.map(a=>{const o={authorName:prim('authorName',a.name)};if(a.affiliation)o.authorAffiliation=prim('authorAffiliation',a.affiliation);if(a.orcid){o.authorIdentifierScheme={typeName:'authorIdentifierScheme',multiple:false,typeClass:'controlledVocabulary',value:'ORCID'};o.authorIdentifier=prim('authorIdentifier',a.orcid);}return o;})));
fields.push(compound('datasetContact',cfg.contact.map(c=>{const o={datasetContactEmail:prim('datasetContactEmail',c.email)};if(c.name)o.datasetContactName=prim('datasetContactName',c.name);if(c.affiliation)o.datasetContactAffiliation=prim('datasetContactAffiliation',c.affiliation);return o;})));
fields.push(compound('dsDescription',[{dsDescriptionValue:prim('dsDescriptionValue',cfg.description)}]));
fields.push(controlled('subject',cfg.subjects&&cfg.subjects.length?cfg.subjects:['Social Sciences']));
if(cfg.keywords&&cfg.keywords.length)fields.push(compound('keyword',cfg.keywords.map(k=>({keywordValue:prim('keywordValue',k)}))));
if(cfg.kindOfData&&cfg.kindOfData.length)fields.push(primList('kindOfData',cfg.kindOfData));
if(cfg.language)fields.push(controlled('language',[cfg.language]));
if(cfg.depositor)fields.push(prim('depositor',cfg.depositor));
fields.push(prim('dateOfDeposit',new Date().toISOString().slice(0,10)));
if(cfg.timePeriodStart||cfg.timePeriodEnd){const o={};if(cfg.timePeriodStart)o.timePeriodCoveredStart=prim('timePeriodCoveredStart',cfg.timePeriodStart);if(cfg.timePeriodEnd)o.timePeriodCoveredEnd=prim('timePeriodCoveredEnd',cfg.timePeriodEnd);fields.push(compound('timePeriodCovered',[o]));}
if(cfg.relatedPublication)fields.push(compound('publication',[{publicationCitation:prim('publicationCitation',cfg.relatedPublication)}]));
if(cfg.relatedMaterial&&cfg.relatedMaterial.length)fields.push(primList('relatedMaterial',cfg.relatedMaterial));
fields.push(prim('softwareVersion','blob-da-market-pipeline 1.0.0'));
// URIs as registered on Harvard Dataverse (GET /api/licenses)
const LICENSE_URI={'CC0 1.0':'http://creativecommons.org/publicdomain/zero/1.0','CC BY 4.0':'http://creativecommons.org/licenses/by/4.0'};
return{datasetVersion:{license:{name:cfg.license||'CC0 1.0',uri:LICENSE_URI[cfg.license||'CC0 1.0']},metadataBlocks:{citation:{displayName:'Citation Metadata',name:'citation',fields}}}};}
function hashFile(file){return new Promise((res,rej)=>{const s256=crypto.createHash('sha256'),smd5=crypto.createHash('md5'),ssha1=crypto.createHash('sha1');const st=fs.createReadStream(file);st.on('error',rej);st.on('data',b=>{s256.update(b);smd5.update(b);ssha1.update(b);});st.on('end',()=>res({sha256:s256.digest('hex'),md5:smd5.digest('hex'),sha1:ssha1.digest('hex')}));});}
async function describeFile(duck,file){const ext=path.extname(file).toLowerCase();let src=null;
if(ext==='.parquet')src=`read_parquet('${file.replaceAll("'","''")}')`;
else if(ext==='.csv')src=`read_csv('${file.replaceAll("'","''")}',header=true,sample_size=200000)`;
if(!src)return null;
try{const cols=await duck.all(`DESCRIBE SELECT * FROM ${src}`);const cnt=await duck.all(`SELECT count(*) AS n FROM ${src}`);return{columns:cols.map(c=>({name:c.column_name,type:c.column_type})),rows:Number(cnt[0].n)};}catch(e){return{error:String(e.message||e)};}}
async function splitIfOversized(duck,file,limitBytes){const size=fs.statSync(file).size;if(size<=limitBytes)return[file];
if(path.extname(file)!=='.parquet'){console.log('WARNING:',path.basename(file),'is',(size/1048576).toFixed(0),'MB and exceeds the per-file limit but cannot be split automatically; compress it or raise MAX_FILE_MB');return[file];}
const q=`read_parquet('${file.replaceAll("'","''")}')`;
let cols;try{cols=(await duck.all(`DESCRIBE SELECT * FROM ${q}`)).map(c=>c.column_name);}catch{return[file];}
const key=['date','block_time','ts'].find(c=>cols.includes(c));
if(!key){console.log('WARNING:',path.basename(file),'exceeds the per-file limit and has no date column to split on');return[file];}
const years=(await duck.all(`SELECT DISTINCT year(${key}) AS y FROM ${q} ORDER BY y`)).map(r=>Number(r.y));
const base=file.replace(/\.parquet$/,'');const out=[];
for(const y of years){const dst=`${base}_${y}.parquet`;await duck.run(`COPY (SELECT * FROM ${q} WHERE year(${key})=${y}) TO '${dst.replaceAll("'","''")}' (FORMAT PARQUET,COMPRESSION ZSTD)`);out.push(dst);}
fs.rmSync(file);console.log('split',path.basename(file),'into',out.length,'yearly parts to stay under the per-file limit');return out;}
async function main(){
if(!fs.existsSync(OUT_DIR)){console.error(`missing ${OUT_DIR}/: run 08_validate_merge.js first`);process.exit(1);}
const cfgPath='deposit.config.json';
if(!fs.existsSync(cfgPath)){saveJsonAtomic(cfgPath,TEMPLATE);console.error('created deposit.config.json from a template; fill in author, contact email, and license, then re-run this script');process.exit(2);}
const cfg=loadJson(cfgPath,null);
const problems=[];
if(!cfg.authors||!cfg.authors.length||/Firstname/.test(cfg.authors[0].name))problems.push('authors[0].name is still the placeholder');
if(!cfg.contact||!cfg.contact.length||!cfg.contact[0].email||/example\.edu/.test(cfg.contact[0].email))problems.push('contact[0].email is still the placeholder');
if(problems.length){console.error('deposit.config.json is incomplete:');for(const p of problems)console.error(' -',p);process.exit(2);}
if(fs.existsSync(RELEASE)&&fs.readdirSync(RELEASE).length&&process.env.ALLOW_OVERWRITE_RELEASE!=='1'){console.error(`${RELEASE}/ exists and is not empty: it may be the deposited archive. Package into a new directory (RELEASE_DIR=release_vN) or set ALLOW_OVERWRITE_RELEASE=1.`);process.exit(2);}
fs.rmSync(RELEASE,{recursive:true,force:true});ensureDir(RELEASE);
const staged=[];
// Exchange price data are not redistributed (their terms restrict it); script 05 regenerates them.
const EXCLUDE=new Set((process.env.RELEASE_EXCLUDE??'prices_daily.csv').split(',').filter(Boolean));
for(const f of fs.readdirSync(OUT_DIR)){if(EXCLUDE.has(f))continue;const src=path.join(OUT_DIR,f);if(fs.statSync(src).isFile()){fs.copyFileSync(src,path.join(RELEASE,f));staged.push(f);}}
for(const[src,dst]of[['docs/PIPELINE.md','README.md'],['DATASETS.md','DATASETS.md']]){if(fs.existsSync(src))fs.copyFileSync(src,path.join(RELEASE,dst));}
const vr=path.join('reports','validation_report.json');
if(fs.existsSync(vr))fs.copyFileSync(vr,path.join(RELEASE,'validation_report.json'));
if(INCLUDE_SOURCE){const{execSync}=await import('node:child_process');const list=['package.json','config.js','lib','README.md','DATASETS.md',...fs.readdirSync('.').filter(f=>/^\d\d_.*\.js$/.test(f))].filter(f=>fs.existsSync(f));
try{execSync(`tar -czf ${path.join(RELEASE,'pipeline-source.tar.gz')} ${list.map(f=>JSON.stringify(f)).join(' ')}`,{stdio:'ignore'});console.log('bundled pipeline source as pipeline-source.tar.gz');}catch(e){console.log('could not create pipeline-source.tar.gz:',String(e.message||e));}}
const duck=openDuck(':memory:');
const limit=MAX_MB*1048576;
let files=fs.readdirSync(RELEASE).map(f=>path.join(RELEASE,f));
const expanded=[];
for(const f of files)expanded.push(...await splitIfOversized(duck,f,limit));
files=expanded.sort();
const manifest={generated_at:new Date().toISOString(),generator:'blob-da-market-pipeline 09_package_release.js',fork_config:FORKS,per_file_size_limit_mb:MAX_MB,files:[]};
const codebook=['# Codebook','','Generated automatically from the deposited files. Field semantics, units, and caveats are documented in `DATASETS.md`; this file records the exact structure and size of the data as deposited.','',`Generated: ${manifest.generated_at}`,''];
for(const f of files){const name=path.basename(f);const size=fs.statSync(f).size;const h=await hashFile(f);
const baseKey=name.replace(/_(\d{4})\.parquet$/,'.parquet');
const doc=FILE_DOCS[name]||FILE_DOCS[baseKey]||{d:'',c:['Data']};
const desc=FILE_DOCS[name]?doc.d:(FILE_DOCS[baseKey]?doc.d+' Partitioned by year for deposit; this part covers '+(name.match(/_(\d{4})\.parquet$/)||[,''])[1]+'.':'');
const info=await describeFile(duck,f);
manifest.files.push({name,bytes:size,sha256:h.sha256,md5:h.md5,sha1:h.sha1,rows:info&&info.rows!=null?info.rows:null,columns:info&&info.columns?info.columns.length:null,description:desc,categories:doc.c});
codebook.push(`## ${name}`,'',desc||'(no description)','',`- Size: ${(size/1048576).toFixed(2)} MB`,`- SHA-256: \`${h.sha256}\``);
if(info&&info.rows!=null)codebook.push(`- Rows: ${info.rows.toLocaleString('en-US')}`);
if(info&&info.columns){codebook.push('','| column | type |','|---|---|');for(const c of info.columns)codebook.push(`| ${c.name} | ${c.type} |`);}
codebook.push('');}
await duck.close();
const addAux=async name=>{const p=path.join(RELEASE,name);const h=await hashFile(p);const doc=FILE_DOCS[name]||{d:'',c:['Documentation']};manifest.files.push({name,bytes:fs.statSync(p).size,sha256:h.sha256,md5:h.md5,sha1:h.sha1,rows:null,columns:null,description:doc.d,categories:doc.c});};
fs.writeFileSync(path.join(RELEASE,'CODEBOOK.md'),codebook.join('\n'));
await addAux('CODEBOOK.md');
fs.writeFileSync(path.join(RELEASE,'MANIFEST-SHA256.txt'),manifest.files.map(f=>`${f.sha256}  ${f.name}`).join('\n')+'\n');
await addAux('MANIFEST-SHA256.txt');
manifest.files.sort((a,b)=>a.name<b.name?-1:1);
saveJsonAtomic(path.join(RELEASE,'manifest.json'),manifest);
saveJsonAtomic(path.join(RELEASE,'dataverse_dataset.json'),buildCitation(cfg));
const total=manifest.files.reduce((a,f)=>a+f.bytes,0);
const over=manifest.files.filter(f=>f.bytes>limit);
console.log(`bundle ready in ${RELEASE}/: ${manifest.files.length} files, ${(total/1048576).toFixed(1)} MB total`);
if(over.length)console.log('WARNING: still over the per-file limit:',over.map(f=>f.name).join(', '));
console.log('next: DATAVERSE_URL=... DATAVERSE_TOKEN=... DATAVERSE_PARENT=... npm run deposit');}
main().catch(e=>{console.error(e);process.exit(1);});
