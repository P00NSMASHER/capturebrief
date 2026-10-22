'use strict';
const DAY=86400000;
function ms(date){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(date))) throw Error('Use YYYY-MM-DD');
 const value=Date.parse(date+'T00:00:00Z');
 if(!Number.isFinite(value)||new Date(value).toISOString().slice(0,10)!==date) throw Error('Invalid date');
 return value;
}
const iso=t=>new Date(t).toISOString().slice(0,10);
function workday(t,holidays){const day=new Date(t).getUTCDay();return day!==0&&day!==6&&!holidays.has(iso(t));}
function businessDaysAfter(date,count,holidays=new Set()){
 if(!Number.isSafeInteger(count)||count<0||count>30) throw Error('Invalid business-day count');
 let t=ms(date);
 while(count>0){t+=DAY;if(workday(t,holidays))--count;}
 return iso(t);
}
function nextBusinessDay(date,holidays=new Set()){
 let t=ms(date);while(!workday(t,holidays))t+=DAY;return iso(t);
}
function plan({intakeDate,acceptanceDate,deliveryDate,holidays=[]}){
 const ignored=new Set(holidays);
 return {responseDue:businessDaysAfter(intakeDate,2,ignored),
  briefDue:acceptanceDate?businessDaysAfter(acceptanceDate,5,ignored):null,
  checkpoints:deliveryDate?[7,14].map(n=>nextBusinessDay(iso(ms(deliveryDate)+DAY*n),ignored)):[]};
}
module.exports={businessDaysAfter,nextBusinessDay,plan};