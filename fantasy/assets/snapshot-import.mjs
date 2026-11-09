/* Private Brock Hard snapshot import: no network or credential handling. */
export const OWNER_LEAGUE='470.l.290846', OWNER_TEAM='2';
const pick=(data,keys)=>Object.fromEntries(keys.filter(k=>Object.prototype.hasOwnProperty.call(data||{},k)).map(k=>[k,data[k]]));
const isRecord=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const only=(x,keys)=>isRecord(x)?pick(x,keys):{};
const playerKeys=['id','name','position','slot','eligiblePositions','nflTeam','team','injury','actualPoints','locked','cantCut','editable'];
const availableKeys=['id','name','position','eligiblePositions','team','acquisitionState','waiverDate','percentOwned'];
const matchKeys=['teamKey','teamId','teamName','name','points','projectedPoints','liveProjectedPoints','winProbability'];
export function preparePrivateImport(raw,{now=Date.now(),previousIso=null}={}){
 if(!isRecord(raw)||raw.schemaVersion!==3)throw Error('A schema-version-3 Yahoo JSON capture is required');
 const t=raw.teams?.brock;
 if(!isRecord(t)||String(t.leagueId)!==OWNER_LEAGUE||String(t.teamId)!==OWNER_TEAM)
   throw Error('This file is not for Brock Hard in the connected Yahoo league');
 if(raw.season!==2026||!Number.isInteger(raw.week)||raw.week<1||raw.week>25)
   throw Error('Missing or invalid Yahoo season/week');
 const time=Date.parse(raw.syncedAtIso);
 if(!Number.isFinite(time)||time>now+300_000)throw Error('Capture timestamp missing or in the future');
 const older=Date.parse(previousIso??'');
 if(Number.isFinite(older)&&time<=older)
   throw Error('This capture is not newer than the one saved on this device');
 if(!Array.isArray(t.roster)||t.roster.length===0||t.roster.length>60)
   throw Error('Current Brock Hard roster is missing or invalid');
 const seen=new Set();
 const roster=t.roster.map(p=>{
   if(!isRecord(p)||!p.name||!p.id||!p.slot||!p.position||seen.has(String(p.id)))
     throw Error('Malformed or duplicated roster player');
   seen.add(String(p.id));
   return {...pick(p,playerKeys),projection:null};
 });
 if(!isRecord(t.lineupSlots)||Object.entries(t.lineupSlots).some(([k,v])=>!k||!Number.isInteger(v)||v<0||v>15))
   throw Error('Yahoo lineup rules are missing or malformed');
 if(t.availablePlayers!==undefined&&!Array.isArray(t.availablePlayers))
   throw Error('Available-player inventory is malformed');
 if((t.availablePlayers||[]).length>1000)throw Error('Available-player inventory too large');
 const availablePlayers=(t.availablePlayers||[]).map(p=>{
  if(!isRecord(p)||!p.id||!p.name||!p.position)throw Error('Available-player identity missing');
  return {...pick(p,availableKeys),projection:null};
 });
 const match=isRecord(t.matchup)?{
  ...pick(t.matchup,['status']),
  home:only(t.matchup.home,matchKeys),away:only(t.matchup.away,matchKeys)
 }:null;
 const transactionKeys=['date','move','team','type'];
 const transactions=Array.isArray(t.transactions)?t.transactions.slice(0,50).filter(isRecord).map(p=>pick(p,transactionKeys)):[];
 const top=pick(raw,['schemaVersion','provider','season','week','syncedAtIso','source','captureType']);
 return {...top,teams:{brock:{
  ...pick(t,['name','short','accent','leagueId','teamId','leagueUrl','provider','record','rank','waiver','score','scoreState','nextMove','nextDetail','confidence','health','weekNote']),
  roster,lineupSlots:t.lineupSlots,availablePlayers,matchup:match,
  transactions,transactionsCoverage:only(t.transactionsCoverage,['limited','includedRows','providerRowsReported','window']),
  projectionCoverage:'none'
 }}};
}
