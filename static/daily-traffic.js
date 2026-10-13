'use strict';

const dailyReport=document.getElementById('daily-report');
const dailyRows=Array.from(document.querySelectorAll('[data-daily-traffic-row]'));
const dailyDetailRow=document.getElementById('daily-traffic-detail-row');
const dailyChartCanvas=document.getElementById('daily-traffic-chart');
const dailyCache=new Map();
let selectedDailyRow=null,dailyChart=null,dailyGeneration=0;

const dailyText=(id,value)=>{const element=document.getElementById(id);if(element)element.textContent=value};
const dailyNumber=value=>typeof value==='number'&&Number.isFinite(value)
 ? value.toLocaleString('id-ID',{maximumFractionDigits:1})+' Mbps':'—';
const dailyTimestamp=value=>value?value.replace('T',' '):'—';

function removeDailyChart(){
 if(!dailyChart)return;
 const index=netmonCharts.indexOf(dailyChart);
 if(index>=0)netmonCharts.splice(index,1);
 dailyChart.destroy();
 dailyChart=null;
}

async function fetchDailyTraffic(label){
 const response=await fetch('/api/daily-traffic/'+encodeURIComponent(label)+'?end_at='+encodeURIComponent(dailyReport.dataset.windowEnd));
 if(response.status===401){window.location.href='/login';throw new Error('Sesi berakhir. Silakan login kembali.')}
 if(!response.ok)throw new Error('Detail traffic harian gagal dimuat. Muat ulang halaman untuk mencoba kembali.');
 return response.json();
}

function renderDailyTraffic(row,data){
 const samples=Array.isArray(data.samples)?data.samples:[];
 const validSamples=samples.filter(sample=>Number.isFinite(sample.input_mbps)||Number.isFinite(sample.output_mbps));
 dailyText('daily-traffic-title',row.dataset.label);
 dailyText('daily-traffic-period',`Periode ${data.start_at}–${data.end_at}`);
 dailyText('daily-sample-count',String(validSamples.length));

 for(const [key,id,timeId] of [
  ['input_mbps','daily-peak-input','daily-peak-input-time'],
  ['output_mbps','daily-peak-output','daily-peak-output-time'],
 ]){
  let peak=null,peakAt=null;
  for(const sample of validSamples){
   const value=sample[key];
   if(Number.isFinite(value)&&(peak===null||value>peak)){peak=value;peakAt=sample.timestamp}
  }
  dailyText(id,dailyNumber(peak));
  dailyText(timeId,dailyTimestamp(peakAt));
 }

 removeDailyChart();
 dailyChart=makeChart(dailyChartCanvas,samples,'wan',false,{wanLimit:data.limit_mbps});
 if(!validSamples.length){
  dailyText('daily-traffic-message',`Belum ada sampel koleksi SSH live pada periode ${data.start_time}–sekarang.`);
 }else{
  dailyText('daily-traffic-message',`Garis putus-putus menunjukkan batas ${dailyNumber(data.limit_mbps)}. Grafik memakai sampel koleksi SSH live; rate interface adalah rata-rata 5 menit.`);
 }
}

async function openDailyTraffic(row){
 const generation=++dailyGeneration;
 dailyText('daily-traffic-title',row.dataset.label);
 dailyText('daily-traffic-period','Memuat periode report…');
 dailyText('daily-traffic-message','Memuat grafik traffic…');
 const cached=dailyCache.get(row.dataset.label);
 if(cached){renderDailyTraffic(row,cached);return}
 try{
  const data=await fetchDailyTraffic(row.dataset.label);
  if(generation!==dailyGeneration||row!==selectedDailyRow)return;
  dailyCache.set(row.dataset.label,data);
  renderDailyTraffic(row,data);
 }catch(error){
  if(generation!==dailyGeneration||row!==selectedDailyRow)return;
  dailyText('daily-traffic-period',`Periode ${dailyReport.dataset.startAt}–${dailyReport.dataset.endAt}`);
  dailyText('daily-traffic-message',error.message);
 }
}

function selectDailyRow(row){
 if(row&&row===selectedDailyRow)row=null;
 const previousRow=selectedDailyRow;
 selectedDailyRow=row;
 for(const item of dailyRows){
  const selected=item===row;
  item.classList.toggle('selected',selected);
  const button=item.querySelector('[data-daily-traffic-select]');
  button.setAttribute('aria-expanded',String(selected));
 }
 if(!row){
  dailyGeneration++;
  dailyDetailRow.hidden=true;
  removeDailyChart();
  return;
 }
 if(previousRow&&previousRow!==row)removeDailyChart();
 row.after(dailyDetailRow);
 dailyDetailRow.hidden=false;
 openDailyTraffic(row);
 requestAnimationFrame(()=>{
  if(row===selectedDailyRow){
   const behavior=window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth';
   dailyDetailRow.scrollIntoView({behavior,block:'nearest'});
  }
 });
}

if(dailyReport&&dailyRows.length){
 for(const row of dailyRows){
  row.querySelector('[data-daily-traffic-select]').addEventListener('click',()=>selectDailyRow(row));
 }
}
