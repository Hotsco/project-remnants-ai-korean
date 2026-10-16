'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('npc-settings-token') || '';
if (token) sessionStorage.setItem('npc-settings-token', token);
history.replaceState(null, '', location.pathname);
let snapshot = null, npc = null, selectedSave = '', busy = false, running = null, closed = false;
const fields = [...document.querySelectorAll('[data-field]')];
function message(text, kind = '') { $('notice').textContent = text; $('notice').className = 'notice ' + kind; }
function dirty() { return npc && $('profile').value !== npc.profile; }
function hasDraft() { return dirty() || fields.some(field => field.value.trim()); }
function statusLabel(text) { $('saved-state').textContent = text; }
function update() {
  const active = !!npc && !busy && !closed;
  $('profile').disabled = !active;
  fields.forEach(field => field.disabled = !active);
  for (const id of ['reload','verify','compose']) $(id).disabled = !active;
  $('save').disabled = !active || running !== false || $('profile').value.length > (snapshot?.limit ?? Infinity);
  for (const id of ['saves','refresh','configure','quit','game','mod','userdata']) $(id).disabled = busy || closed;
  for (const button of document.querySelectorAll('[data-choose], .npc-item')) button.disabled = busy || closed;
  $('count').textContent = `${$('profile').value.length.toLocaleString()}${snapshot ? ' / ' + snapshot.limit.toLocaleString() : ''}자`;
}
async function api(route, data) {
  const response = await fetch('/api/' + route, {method: data === undefined ? 'GET' : 'POST',
    headers: {'X-NPC-Token':token, ...(data === undefined ? {} : {'Content-Type':'application/json'})},
    ...(data === undefined ? {} : {body:JSON.stringify(data)})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '요청을 완료하지 못했습니다.');
  return result;
}
async function task(text, action) {
  if (busy || closed) return;
  busy = true; update(); message(text);
  try { await action(); } catch(error) { message(error.message, 'error'); }
  finally { busy = false; update(); }
}
function applyStatus(state) {
  running = state.running;
  $('game-status').textContent = running === true ? '게임 실행 중 · 저장 잠김' : running === false ? '게임 종료됨 · 저장 가능' : '게임 상태 확인 실패 · 저장 잠김';
  $('game-status').title = state.error || '';
  update();
}
function confirmChoice(text, label='계속') {
  return new Promise(resolve => {
    const dialog=$('confirm-dialog');
    $('confirm-message').textContent=text; $('confirm-ok').textContent=label;
    const finish=answer=>{dialog.close(); resolve(answer);};
    $('confirm-ok').onclick=()=>finish(true); $('confirm-cancel').onclick=()=>finish(false);
    dialog.oncancel=event=>{event.preventDefault(); finish(false);};
    dialog.showModal(); $('confirm-cancel').focus();
  });
}
async function discard() { return !hasDraft() || await confirmChoice('아직 저장하지 않은 작성 내용이 있습니다. 변경 내용을 버릴까요?','변경 내용 버리기'); }
function selectNpc(id) {
  npc = snapshot.npcs.find(item => item.id === id) || null;
  fields.forEach(field => field.value = '');
  $('template').open = false;
  $('profile').value = npc?.profile ?? '';
  $('npc-name').textContent = npc?.name || 'NPC를 선택하세요';
  $('npc-meta').textContent = npc ? `${npc.female ? '여성' : '남성'} · ${npc.dead ? '사망' : '생존'} · ${npc.id.slice(0,8)}` : '이 세이브에는 저장된 NPC가 없습니다.';
  $('backup-details').hidden = true;
  statusLabel(npc ? '세이브에서 불러옴' : '선택 전');
  renderNpcs(); update();
}
function renderNpcs() {
  $('npc-list').replaceChildren();
  if (!snapshot?.npcs.length) { const p = document.createElement('p'); p.textContent = '저장된 NPC가 없습니다.'; p.className='muted'; $('npc-list').append(p); return; }
  snapshot.npcs.forEach(row => {
    const button = document.createElement('button'); button.className = 'npc-item' + (npc?.id === row.id ? ' selected' : '');
    button.setAttribute('aria-pressed', String(npc?.id === row.id));
    const name = document.createElement('strong'); name.textContent = row.name || '이름 없음';
    const info = document.createElement('small'); info.textContent = (row.profile ? '프로필 있음' : '프로필 비어 있음') + ' · ' + row.id.slice(0,8);
    button.append(name,info); button.onclick = async () => { if (!busy && await discard()) { selectNpc(row.id); message('선택한 NPC의 저장된 프로필입니다.'); } };
    $('npc-list').append(button);
  });
}
async function bootstrap() {
  const result = await api('bootstrap');
  for (const key of ['game','mod','userdata']) $(key).value = result.settings[key] || '';
  $('mod-choices').replaceChildren();
  (result.settings.mod_choices || []).forEach(path => { const o = document.createElement('option'); o.value = path; $('mod-choices').append(o); });
  $('saves').replaceChildren(new Option('세이브를 선택하세요', ''));
  result.saves.forEach(save => $('saves').add(new Option(`${save.name} (${save.mode})`, save.id)));
  snapshot = null; npc = null; selectedSave = ''; $('profile').value = ''; $('npc-name').textContent = 'NPC를 선택하세요';
  $('npc-meta').textContent = '기존 프로필을 그대로 불러옵니다.'; $('npc-list').replaceChildren(); statusLabel('선택 전');
  applyStatus(result.status);
  $('locations').open = !result.settings.game || !result.settings.mod;
  message(result.saves.length ? '편집할 세이브를 선택해주세요.' : '저장된 NPC가 있는 세이브를 찾지 못했습니다. 사용자 데이터 폴더를 확인해주세요.');
}
$('saves').onchange = async () => {
  const id = $('saves').value;
  if (!await discard()) { $('saves').value = selectedSave; return; }
  if (!id) { snapshot = null; npc = null; selectedSave = ''; $('profile').value=''; $('npc-list').replaceChildren(); $('npc-name').textContent='NPC를 선택하세요'; update(); return; }
  task('NPC와 기존 프로필을 불러오고 있습니다…', async () => {
    try { snapshot = await api('load',{save:id}); }
    catch (error) { $('saves').value=selectedSave; throw error; }
    selectedSave = id; selectNpc(snapshot.npcs[0]?.id); message(snapshot.npcs.length ? '기존 프로필을 불러왔습니다.' : '이 세이브에는 저장된 NPC가 없습니다.');
  });
};
$('profile').oninput = () => { statusLabel(dirty() ? '저장하지 않은 변경' : '불러온 내용과 같음'); update(); };
$('reload').onclick = async () => { if (await discard()) task('세이브에서 다시 읽고 있습니다…',async () => {
  const id=npc.id; snapshot=await api('load',{save:selectedSave}); selectNpc(id); message('현재 세이브의 프로필을 다시 불러왔습니다.');
}); };
$('verify').onclick = () => task('저장된 내용과 비교하고 있습니다…',async () => {
  const fresh=await api('load',{save:selectedSave}); const found=fresh.npcs.find(row=>row.id===npc.id);
  if (found && found.profile === $('profile').value) {
    snapshot=fresh; npc=found; statusLabel('저장 내용 일치'); renderNpcs(); message('현재 입력 내용이 세이브에 저장된 프로필과 일치합니다.','success');
  } else { statusLabel('저장 내용과 다름'); message('현재 입력 내용과 세이브의 프로필이 다릅니다. 저장된 내용을 보려면 다시 불러오기를 눌러주세요.','error'); }
});
$('save').onclick = async () => {
  if (!npc || running !== false) return;
  if (!$('profile').value.trim() && npc.profile && !await confirmChoice('이 NPC의 프로필을 비우고 저장할까요?','비우고 저장')) return;
  task('프로필을 저장하고, 세이브에서 다시 읽어 확인하고 있습니다…', async () => {
    const id=npc.id;
    const result=await api('save',{save:selectedSave,npc:id,profile:$('profile').value,etag:snapshot.etag});
    if (!result.verified) throw new Error('저장 결과를 확인하지 못했습니다.');
    snapshot=result.snapshot; selectNpc(id); statusLabel('저장 확인 완료');
    message('저장 확인 완료. 세이브에서 다시 읽은 프로필이 입력한 내용과 일치합니다.','success');
    if (result.backup) { $('backup-details').hidden=false; $('backup-path').textContent=result.backup; }
  });
};
$('compose').onclick = async () => {
  const composed=fields.filter(field=>field.value.trim()).map(field=>`${field.dataset.field}: ${field.value.trim()}`).join('\n');
  if (!composed) return message('작성할 항목을 하나 이상 입력해주세요.');
  if ($('profile').value.trim() && !await confirmChoice('작성한 항목으로 현재 프로필 입력란을 바꿀까요? 저장 버튼을 누르기 전까지 세이브는 바뀌지 않습니다.','입력란 바꾸기')) return;
  $('profile').value=composed; $('profile').oninput(); message('입력란에 반영했습니다. 내용을 확인한 뒤 저장해주세요.');
};
$('refresh').onclick = async () => { if(await discard()) task('목록을 새로 불러오고 있습니다…',bootstrap); };
$('configure').onclick = async () => { if(await discard()) task('설치 위치를 확인하고 있습니다…',async () => {
  await api('configure',Object.fromEntries(['game','mod','userdata'].map(key=>[key,$(key).value]))); await bootstrap();
}); };
document.querySelectorAll('[data-choose]').forEach(button=>button.onclick=()=>task('위치 선택창에서 폴더 또는 파일을 선택해주세요.',async()=>{
  const result=await api('choose',{kind:button.dataset.choose}); $(button.dataset.choose).value=result.path; message('위치를 선택했습니다. 위치 적용을 눌러주세요.');
}));
$('quit').onclick = async () => { if(await discard()) task('설정창을 종료하고 있습니다…',async()=>{
  await api('quit',{}); closed=true; message('설정창을 종료했습니다. 이 창을 닫아도 됩니다.');
}); };
window.addEventListener('beforeunload',event=>{if(hasDraft()&&!closed){event.preventDefault();event.returnValue='';}});
let statusTimer, statusPending = false;
function scheduleStatus() {
  clearTimeout(statusTimer);
  if (!document.hidden && !closed) statusTimer = setTimeout(refreshStatus, 15000);
}
async function refreshStatus() {
  clearTimeout(statusTimer);
  if (document.hidden || closed) return;
  if (busy || statusPending) { scheduleStatus(); return; }
  statusPending = true;
  try { applyStatus(await api('status')); }
  catch { running=null; update(); $('game-status').textContent='연결 끊김'; }
  finally { statusPending=false; scheduleStatus(); }
}
document.addEventListener('visibilitychange', () => {
  clearTimeout(statusTimer);
  if (!document.hidden && !closed) {
    running=null; update(); $('game-status').textContent='게임 상태 확인 중';
    refreshStatus();
  }
});
task('세이브 목록을 불러오고 있습니다…',bootstrap).finally(scheduleStatus);
