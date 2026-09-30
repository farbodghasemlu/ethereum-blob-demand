import duckdb from 'duckdb';
export function openDuck(file){const db=new duckdb.Database(file);const con=db.connect();const all=sql=>new Promise((res,rej)=>con.all(sql,(e,r)=>e?rej(e):res(r)));const run=sql=>new Promise((res,rej)=>con.run(sql,e=>e?rej(e):res()));const close=()=>new Promise(res=>db.close(()=>res()));return{db,con,all,run,close};}
