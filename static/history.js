'use strict';

const historyDashboard=document.getElementById('history-dashboard');
const historyRows=Array.from(document.querySelectorAll('[data-history-row]'));
const historyCache=new Map();
let selectedHistoryRow=null,detailChart=null,historyGeneration=0,detailGeneration=0,historyFilter='all';
const historyDays=document.getElementById('history-days');
const historySearch=document.getElementById('history-search');
const historyDetail=document.getElementById('history-detail');
const historyDetailRow=document.getElementById('history-detail-row');
const wanLimit=Number(historyDashboard?.dataset.wanLimit||300);
const historyText=(id,text)=>{const element=document.getElementById(id);if(element)element.textContent=text};
const historyStamp=stamp=>stamp?stamp.replace('T',' '):'—';
const historyValue=(value,type)=>typeof value==='number'&&Number.isFinite(value)
 ? value.toLocaleString('id-ID',{maximumFractionDigits:1})+(type==='wan'?' Mbps':'%'):'—';
const historyFields=type=>type==='wan'
 ? [{label:'Input',key:'input_mbps'},{label:'Output',key:'output_mbps'}]
 : [{label:'CPU',key:'cpu_max'},{label:'Memory',key:'mem_pct'}];

function removeHistoryChart(chart){
 if(!chart)return;
 const index=netmonCharts.indexOf(chart);
 if(index>=0)netmonCharts.splice(index,1);
 chart.destroy();
}

function setRowCell(row,selector,text){
 const cell=row.querySelector(selector);
 if(cell)cell.textContent=text;
}

function summaryPeak(summary,type){
 if(!summary)return null;
 const fields=historyFields(type);
 const values=fields.map(field=>summary.peaks?.[field.key]?.value).filter(value=>typeof value==='number'&&Number.isFinite(value));
 return values.length?Math.max(...values):null;
}

function renderSummaryRow(row,summary){
 const type=row.dataset.type,fields=historyFields(type),hasData=Boolean(summary?.sample_count);
 fields.forEach((field,index)=>{
  const suffix=index===0?'first':'second';
  setRowCell(row,`[data-latest-${suffix}-label]`,field.label);
  setRowCell(row,`[data-peak-${suffix}-label]`,field.label);
  setRowCell(row,`[data-latest-${suffix}]`,historyValue(summary?.latest?.[field.key],type));
  const peak=summary?.peaks?.[field.key];
  setRowCell(row,`[data-peak-${suffix}]`,historyValue(peak?.value,type));
  setRowCell(row,`[data-peak-${suffix}-time]`,historyStamp(peak?.timestamp));
 });
 setRowCell(row,'[data-latest-time]',historyStamp(summary?.latest_at));
 setRowCell(row,'[data-sample-count]',hasData?String(summary.sample_count):'0');
 const status=row.querySelector('[data-bandwidth-status]');
 if(type==='wan'){
  const peak=summaryPeak(summary,type);
  const state=!hasData?'unknown':peak>wanLimit?'exceeded':peak===wanLimit?'at_limit':'normal';
  const labels={unknown:'Belum ada data',exceeded:'Melebihi batas',at_limit:'Tepat di batas',normal:'Di bawah batas'};
  status.textContent=labels[state];
  status.className=`history-bandwidth-status ${state}`;
 }else{
  status.textContent='Tidak dinilai';
  status.className='history-bandwidth-status not-applicable';
 }
 row.dataset.peak=summaryPeak(summary,type)??'';
 row.dataset.loaded=hasData?'true':'false';
}

function sortSummaryRows(){
 const body=document.getElementById('history-summary-rows');
 const ordered=[...historyRows].sort((a,b)=>{
  const order=(a.dataset.type==='wan'?0:1)-(b.dataset.type==='wan'?0:1);
  if(order)return order;
  if(a.dataset.type==='wan'&&b.dataset.type==='wan'){
   const peakA=Number(a.dataset.peak),peakB=Number(b.dataset.peak);
   if(Number.isFinite(peakA)&&Number.isFinite(peakB)&&peakA!==peakB)return peakB-peakA;
   if(Number.isFinite(peakA)!==Number.isFinite(peakB))return Number.isFinite(peakA)?-1:1;
  }
  return a.dataset.label.localeCompare(b.dataset.label,'id');
 });
 historyDetailRow.remove();
 ordered.forEach(row=>body.appendChild(row));
 if(selectedHistoryRow)selectedHistoryRow.after(historyDetailRow);
 else body.appendChild(historyDetailRow);
}

function filterHistoryRows(){
 const query=historySearch.value.toLocaleLowerCase('id-ID').trim();
 for(const row of historyRows){
  const typeMatches=historyFilter==='all'||row.dataset.type===historyFilter;
  const queryMatches=row.dataset.label.toLocaleLowerCase('id-ID').includes(query);
  row.hidden=!(typeMatches&&queryMatches);
 }
 const visible=historyRows.filter(row=>!row.hidden);
 document.getElementById('history-no-match').hidden=visible.length>0;
 if(selectedHistoryRow?.hidden)selectHistoryRow(null);
}

async function fetchJson(url){
 const response=await fetch(url);
 if(response.status===401){window.location.href='/login';throw new Error('Sesi berakhir. Silakan login kembali.')}
 if(!response.ok)throw new Error('History gagal dimuat. Muat ulang halaman untuk mencoba kembali.');
 return response.json();
}

async function loadHistorySummary(){
 const generation=++historyGeneration;
 historyCache.clear();
 detailGeneration++;
 historyText('history-overview-message','Mengambil ringkasan history…');
 for(const row of historyRows){
  row.dataset.loaded='false';row.dataset.peak='';
  for(const selector of ['[data-latest-first]','[data-latest-second]','[data-peak-first]','[data-peak-second]','[data-latest-time]','[data-peak-first-time]','[data-peak-second-time]'])setRowCell(row,selector,'—');
  setRowCell(row,'[data-sample-count]','—');
  const status=row.querySelector('[data-bandwidth-status]');status.textContent='Memuat…';status.className='history-bandwidth-status';
 }
 try{
  const summaries=await fetchJson('/api/history-summary?days='+historyDays.value);
  if(generation!==historyGeneration)return;
  const summaryMap=new Map(summaries.map(item=>[item.entity_type+'\u0000'+item.entity_label,item]));
  for(const row of historyRows)renderSummaryRow(row,summaryMap.get(row.dataset.type+'\u0000'+row.dataset.label)||null);
  sortSummaryRows();
  const loaded=summaries.length;
  historyText('history-overview-message',`${loaded} perangkat/link memiliki data · rentang ${historyDays.selectedOptions[0].textContent}. Peak WAN dibandingkan dengan batas ${wanLimit} Mbps; router/switch tidak dinilai dengan batas bandwidth.`);
  if(selectedHistoryRow)renderHistoryDetail();
 }catch(error){
  if(generation!==historyGeneration)return;
  historyText('history-overview-message',error.message);
  if(selectedHistoryRow)renderHistoryDetail();
 }
}

function renderDetailPoints(row,points){
 const type=row.dataset.type,fields=historyFields(type),validPoints=points.filter(point=>fields.some(field=>typeof point[field.key]==='number'&&Number.isFinite(point[field.key])));
 historyText('history-title',row.dataset.label);
 historyText('history-unit',type==='wan'?'Mbps':'Persentase (%)');
 historyText('history-period',points.length?historyStamp(points[0].timestamp)+' — '+historyStamp(points[points.length-1].timestamp):historyDays.selectedOptions[0].textContent);
 historyText('history-samples',String(validPoints.length));
 document.getElementById('history-chart').setAttribute('aria-label','Grafik history '+row.dataset.label);
 fields.forEach((field,index)=>{
  const prefix=index===0?'first':'second',valid=points.filter(point=>typeof point[field.key]==='number'&&Number.isFinite(point[field.key]));
  historyText(prefix+'-metric-label',field.label+' terakhir');
  historyText(prefix+'-metric-latest',historyValue(points.at(-1)?.[field.key],type));
  const total=valid.reduce((sum,point)=>sum+point[field.key],0);
  const minimum=valid.reduce((value,point)=>Math.min(value,point[field.key]),Infinity);
  let maximum=null,maximumAt=null;
  for(const point of valid){if(maximum===null||point[field.key]>maximum){maximum=point[field.key];maximumAt=point.timestamp}}
  const average=valid.length?total/valid.length:null;
  historyText(prefix+'-metric-summary',`Rata-rata ${historyValue(average,type)} · Min ${historyValue(valid.length?minimum:null,type)} · Peak ${historyValue(maximum,type)}${maximumAt?' · '+historyStamp(maximumAt):''}`);
  historyText('record-'+prefix+'-label',field.label+(type==='wan'?' (Mbps)':' (%)'));
 });
 removeHistoryChart(detailChart);
 detailChart=makeChart(document.getElementById('history-chart'),points,type,false,{wanLimit:type==='wan'?wanLimit:null});
 let message;
 if(!points.length)message='Belum ada catatan pada rentang waktu ini.';
 else if(!validPoints.length)message='Data penggunaan belum berhasil terbaca.';
 else if(type==='wan')message=`Garis putus-putus menunjukkan batas bandwidth ${wanLimit} Mbps. Peak adalah sampel tertinggi yang tersimpan; rate interface Cisco merupakan rata-rata 5 menit, bukan puncak sesaat.`;
 else message='Ringkasan dihitung dari snapshot dalam rentang terpilih; router/switch tidak memiliki batas bandwidth pada halaman ini.';
 historyText('history-message',message);
 const fieldsRows=document.getElementById('history-record-rows');fieldsRows.replaceChildren();
 for(const point of points.slice(-10).reverse()){
  const rowElement=document.createElement('tr');
  for(const value of [historyStamp(point.timestamp),historyValue(point[fields[0].key],type),historyValue(point[fields[1].key],type),point.source]){
   const cell=document.createElement('td');cell.textContent=value??'—';rowElement.appendChild(cell);
  }
  fieldsRows.appendChild(rowElement);
 }
 if(!points.length){
  const rowElement=document.createElement('tr'),cell=document.createElement('td');
  cell.colSpan=4;cell.textContent='Belum ada catatan pada rentang waktu ini.';rowElement.appendChild(cell);fieldsRows.appendChild(rowElement);
 }
}

async function renderHistoryDetail(){
 const row=selectedHistoryRow;if(!row)return;
 historyDetail.hidden=false;
 historyText('history-title',row.dataset.label);
 historyText('history-period','Memuat rentang terpilih…');
 historyText('history-message','Memuat grafik…');
 const cached=historyCache.get(row);
 if(cached){renderDetailPoints(row,cached);return}
 const generation=++detailGeneration;
 try{
  const points=await fetchJson('/api/history/'+encodeURIComponent(row.dataset.label)+'?days='+historyDays.value);
  if(generation!==detailGeneration||row!==selectedHistoryRow)return;
  historyCache.set(row,points);
  renderDetailPoints(row,points);
 }catch(error){
  if(generation!==detailGeneration||row!==selectedHistoryRow)return;
  historyText('history-period',historyDays.selectedOptions[0].textContent);
  historyText('history-message',error.message);
 }
}

function selectHistoryRow(row,updateURL=true){
 if(row&&row===selectedHistoryRow)row=null;
 const previousRow=selectedHistoryRow;
 selectedHistoryRow=row;
 for(const item of historyRows){
  const selected=item===row;item.classList.toggle('selected',selected);
  const button=item.querySelector('[data-history-select]');
  button.setAttribute('aria-pressed',String(selected));
  button.setAttribute('aria-expanded',String(selected));
 }
 if(!row){
  detailGeneration++;
  historyDetailRow.hidden=true;
  removeHistoryChart(detailChart);detailChart=null;
  if(updateURL){const url=new URL(window.location.href);url.searchParams.delete('label');window.history.replaceState(null,'',url)}
  return;
 }
 if(previousRow&&previousRow!==row){removeHistoryChart(detailChart);detailChart=null}
 row.after(historyDetailRow);
 historyDetailRow.hidden=false;
 if(updateURL){const url=new URL(window.location.href);url.searchParams.set('label',row.dataset.label);window.history.replaceState(null,'',url)}
 renderHistoryDetail();
 requestAnimationFrame(()=>{
  if(row===selectedHistoryRow)historyDetailRow.scrollIntoView({behavior:'smooth',block:'nearest'});
 });
}

if(historyRows.length){
 for(const row of historyRows)row.querySelector('[data-history-select]').addEventListener('click',()=>selectHistoryRow(row));
 historyDays.addEventListener('change',loadHistorySummary);
 historySearch.addEventListener('input',filterHistoryRows);
 document.querySelectorAll('[data-history-filter]').forEach(button=>button.addEventListener('click',()=>{
  historyFilter=button.dataset.historyFilter;
  document.querySelectorAll('[data-history-filter]').forEach(item=>{
   const active=item===button;item.classList.toggle('active',active);item.setAttribute('aria-pressed',String(active));
  });
  filterHistoryRows();
 }));
 const initialLabel=historyDashboard.dataset.selectedLabel;
 const initialRow=historyRows.find(row=>row.dataset.label===initialLabel);
 if(initialRow)loadHistorySummary().then(()=>selectHistoryRow(initialRow,false));
 else loadHistorySummary();
}
