'use strict';
function refreshThemeLabel(){
  const dark=document.documentElement.dataset.theme==='dark';
  document.querySelectorAll('[data-theme-label]').forEach(el=>el.textContent=dark?'Dark':'Light');
  document.querySelectorAll('[data-theme-toggle]').forEach(el=>el.setAttribute('aria-label',dark?'Ganti ke tema light':'Ganti ke tema dark'));
}
refreshThemeLabel();
document.querySelectorAll('[data-theme-toggle]').forEach(button=>button.addEventListener('click',()=>{
  const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';
  document.documentElement.dataset.theme=theme;
  try{localStorage.setItem('netmon-theme',theme)}catch(e){}
  refreshThemeLabel();window.dispatchEvent(new Event('netmon-theme-change'));
}));
document.querySelectorAll('[data-menu]').forEach(button=>button.addEventListener('click',()=>{
  const open=document.body.classList.toggle('menu-open');
  document.querySelector('.mobile-toggle')?.setAttribute('aria-expanded',String(open));
}));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.body.classList.remove('menu-open');document.querySelector('.mobile-toggle')?.setAttribute('aria-expanded','false')}});
function createConfirmDialog(){
 const dialog=document.createElement('dialog');
 dialog.className='confirm-dialog';
 dialog.setAttribute('role','alertdialog');
 dialog.setAttribute('aria-labelledby','confirm-dialog-title');
 dialog.setAttribute('aria-describedby','confirm-dialog-message');
 dialog.innerHTML='<div class="confirm-card"><span class="confirm-symbol" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6m4-6v6M5 7l1 14h12l1-14M9 7V4h6v3"/></svg></span><div class="confirm-copy"><span class="eyebrow">KONFIRMASI</span><h2 id="confirm-dialog-title">Lanjutkan tindakan?</h2><p id="confirm-dialog-message"></p></div><div class="confirm-actions"><button type="button" class="button confirm-cancel">Batal</button><button type="button" class="button primary confirm-proceed">Lanjutkan</button></div></div>';
 document.body.appendChild(dialog);
 dialog.querySelector('.confirm-cancel').addEventListener('click',()=>dialog.close('cancel'));
 dialog.querySelector('.confirm-proceed').addEventListener('click',()=>dialog.close('confirm'));
 dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close('cancel')});
 return dialog;
}
const confirmDialog=createConfirmDialog();
function askConfirmation({title,message,action}){
 confirmDialog.querySelector('#confirm-dialog-title').textContent=title||'Konfirmasi tindakan';
 confirmDialog.querySelector('#confirm-dialog-message').textContent=message||'Lanjutkan tindakan ini?';
 const actionButton=confirmDialog.querySelector('.confirm-proceed');
 actionButton.textContent=action||'Lanjutkan';
 const destructive=/hapus|delete/i.test(action||title||'');
 confirmDialog.classList.toggle('is-destructive',destructive);
 actionButton.classList.toggle('danger',destructive);
 const previousFocus=document.activeElement;
 return new Promise(resolve=>{
  confirmDialog.addEventListener('close',()=>{
   resolve(confirmDialog.returnValue==='confirm');
   if(previousFocus?.isConnected)previousFocus.focus({preventScroll:true});
  },{once:true});
  confirmDialog.showModal();
  confirmDialog.querySelector('.confirm-cancel').focus();
 });
}
document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',async event=>{
 if(form.dataset.confirmBypass==='true'){delete form.dataset.confirmBypass;return}
 event.preventDefault();
 const accepted=await askConfirmation({title:form.dataset.confirmTitle,message:form.dataset.confirm,action:form.dataset.confirmAction});
 if(!accepted)return;
 form.dataset.confirmBypass='true';
 if(event.submitter)form.requestSubmit(event.submitter);else form.requestSubmit();
}));
document.querySelectorAll('.notice').forEach(notice=>{
 if(notice.classList.contains('error')){notice.setAttribute('role','alert');notice.setAttribute('aria-live','assertive')}
 else{notice.setAttribute('role','status');notice.setAttribute('aria-live','polite')}
 const close=document.createElement('button');close.type='button';close.className='notice-dismiss';close.setAttribute('aria-label','Tutup pemberitahuan');close.textContent='×';
 close.addEventListener('click',()=>{notice.classList.add('notice-closing');notice.addEventListener('animationend',()=>notice.remove(),{once:true})});
 notice.appendChild(close);
});
document.querySelectorAll('form[data-collect]').forEach(form=>form.addEventListener('submit',()=>{
  const button=form.querySelector('button');button.disabled=true;button.querySelector('span').textContent='Collecting…';
  document.querySelector('.collect-progress').hidden=false;
}));
window.addEventListener('pageshow',()=>{document.querySelectorAll('form[data-collect] button').forEach(b=>{b.disabled=false;b.querySelector('span').textContent='Collect Now'});const p=document.querySelector('.collect-progress');if(p)p.hidden=true});
const input=document.getElementById('capture_file'),drop=document.getElementById('dropzone');
if(input&&drop){
 const update=()=>{
  const file=input.files[0],name=document.getElementById('file-name'),size=document.getElementById('file-size');
  document.getElementById('clear-capture').hidden=!file;drop.classList.toggle('has-file',!!file);input.setCustomValidity('');
  name.textContent=file?file.name:'Belum ada file dipilih';
  size.textContent=file?(file.size/1024).toLocaleString('id-ID',{maximumFractionDigits:1})+' KB · Siap diimpor':'Pilih file hasil capture CLI perangkat.';
  if(file&&(!file.name.toLowerCase().endsWith('.txt')||file.size>5*1024*1024)){const message='Gunakan file .txt dengan ukuran maksimal 5 MB.';input.setCustomValidity(message);size.textContent=message}
 };
 input.addEventListener('change',update);
 for(const name of ['dragover','dragleave','drop'])drop.addEventListener(name,e=>{e.preventDefault();drop.classList.toggle('dragover',name==='dragover')});
 drop.addEventListener('drop',e=>{if(e.dataTransfer.files.length){const transfer=new DataTransfer();transfer.items.add(e.dataTransfer.files[0]);input.files=transfer.files;update()}});
 document.getElementById('clear-capture').addEventListener('click',()=>{input.value='';update();input.focus()});
}
function captureTemplateText(id){
 const template=document.querySelector(`[data-capture-template="${id}"]`);
 return template?.textContent.trim()||'';
}
function setTemplateMessage(id,text){
 const message=document.querySelector(`[data-template-message="${id}"]`);
 if(message)message.textContent=text;
}
document.querySelectorAll('[data-template-copy]').forEach(button=>button.addEventListener('click',async()=>{
 const id=button.dataset.templateCopy,text=captureTemplateText(id);
 if(!text){setTemplateMessage(id,'Template tidak tersedia.');return}
 try{
  if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(text);
  else{
   const field=document.createElement('textarea');field.value=text;field.setAttribute('readonly','');field.style.position='fixed';field.style.opacity='0';document.body.appendChild(field);field.select();
   const copied=document.execCommand('copy');field.remove();if(!copied)throw new Error('copy failed');
  }
  setTemplateMessage(id,'Command berhasil disalin.');
 }catch(error){setTemplateMessage(id,'Gagal menyalin. Pilih dan salin teks template secara manual.');}
}));
document.querySelectorAll('[data-template-download]').forEach(button=>button.addEventListener('click',()=>{
 const id=button.dataset.templateDownload,text=captureTemplateText(id);
 if(!text){setTemplateMessage(id,'Template tidak tersedia.');return}
 const blob=new Blob([text+'\n'],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
 link.href=url;link.download=button.dataset.filename||`netmon_capture_${id}.txt`;document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);
 setTemplateMessage(id,'File command berhasil diunduh.');
}));
const captureForm=document.querySelector('[data-capture-form]');
if(captureForm){
 captureForm.addEventListener('submit',()=>{const b=captureForm.querySelector('button[type="submit"]');b.disabled=true;b.querySelector('span').textContent='Mengambil config…';document.querySelector('.capture-progress').hidden=false});
 window.addEventListener('pageshow',()=>{const b=captureForm.querySelector('button[type="submit"]');b.disabled=!document.getElementById('capture-device').options.length||document.getElementById('capture-device').options.length===1;b.querySelector('span').textContent='Show Run';document.querySelector('.capture-progress').hidden=true});
}
document.querySelector('[data-copy-config]')?.addEventListener('click',async()=>{
 const output=document.getElementById('config-output'),message=document.getElementById('copy-message');
 try{await navigator.clipboard.writeText(output.value);message.textContent='Konfigurasi berhasil disalin.'}
 catch(e){output.focus();output.select();message.textContent='Teks dipilih. Tekan Ctrl+C untuk menyalin konfigurasi.'}
});
document.getElementById('backup-search')?.addEventListener('input',e=>{
 let visible=0;document.querySelectorAll('[data-backup-name]').forEach(row=>{row.hidden=!row.dataset.backupName.toLowerCase().includes(e.target.value.toLowerCase().trim());if(!row.hidden)visible++});
 document.getElementById('backup-no-match').hidden=visible>0||!document.querySelector('[data-backup-name]');
});
// Explain the selected connection driver and collection profile without changing them.
const driverDescriptions={
 cisco_ios:'Driver SSH Cisco IOS. Pertahankan jika koneksi perangkat sudah berhasil. Pilihan ini tidak mengatur command monitoring.',
 cisco_xe:'Label driver untuk Cisco IOS XE. Pada versi Netmiko project ini, driver SSH-nya sama dengan cisco_ios; pilih collection profile secara terpisah.'
};
const profileDescriptions={
 classic_ios:'Memory dari show memory statistics (Processor used / total). CPU memakai processes cpu dan CPU history. Pilih jika output ini tersedia pada perangkat.',
 platform_xe:'Memory dari show plat soft stat contr br. CPU mengutamakan processes cpu / history dan fallback ke CPU platform. Pilih jika command dan format output didukung.'
};
for(const [id,help,descriptions] of [['device_type','device-type-help',driverDescriptions],['profile','profile-help',profileDescriptions]]){
 const field=document.getElementById(id),note=document.getElementById(help);
 if(field&&note){const update=()=>note.textContent=descriptions[field.value]||'';field.addEventListener('change',update);update()}
}
document.querySelector('[data-reveal-password]')?.addEventListener('click',e=>{
 const field=document.getElementById('password'),show=field.type==='password';field.type=show?'text':'password';e.currentTarget.textContent=show?'Sembunyikan':'Lihat';e.currentTarget.setAttribute('aria-pressed',String(show));
});
// This is the local application status, not the health of monitored devices.
const localStatus=document.querySelector('[data-local-status]');
let localStatusPending=false;
async function checkLocalStatus(){
 if(!localStatus||document.hidden||localStatusPending)return;
 localStatusPending=true;
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
 try{
  const response=await fetch('/api/local-status',{cache:'no-store',signal:controller.signal});
  if(response.status===401){localStatus.dataset.localStatus='session';localStatus.querySelector('[data-local-label]').textContent='Sesi berakhir';localStatus.querySelector('[data-local-detail]').textContent='Login kembali untuk melanjutkan.';return}
  if(!response.ok)throw new Error('unavailable');
  const data=await response.json();if(data.status!=='online')throw new Error('unavailable');
  localStatus.dataset.localStatus='online';localStatus.querySelector('[data-local-label]').textContent='Local Online';localStatus.querySelector('[data-local-detail]').textContent='Tools berjalan di komputer ini.';
 }catch(e){localStatus.dataset.localStatus='offline';localStatus.querySelector('[data-local-label]').textContent='Local Offline';localStatus.querySelector('[data-local-detail]').textContent='Koneksi ke aplikasi terputus.'}
 finally{clearTimeout(timeout);localStatusPending=false}
}
if(localStatus){checkLocalStatus();setInterval(checkLocalStatus,30000);document.addEventListener('visibilitychange',checkLocalStatus)}
