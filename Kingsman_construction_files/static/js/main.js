// =============================
// Collapsible (safe variant)
// Only toggles when the next sibling is .collapsible-content
// =============================
document.querySelectorAll('.collapsible-button').forEach(button => {
  const content = button.nextElementSibling;
  const icon = button.querySelector('.icon');
  if (!content || !content.classList.contains('collapsible-content')) return;

  button.addEventListener('click', () => {
    const open = content.style.display === 'block';
    content.style.display = open ? 'none' : 'block';
    if (icon) icon.textContent = open ? '+' : '–';
  });
});

// =============================
// Jobs: modal open/close + create
// =============================
(function(){
  const modal  = document.getElementById('jobModal');
  const openBtn= document.getElementById('btnNewJob');
  const closeX = document.getElementById('jobClose');
  const cancel = document.getElementById('jobCancel');
  const form   = document.getElementById('jobForm');
  const msg    = document.getElementById('jobMsg');

  function openModal(){ if (modal?.showModal) modal.showModal(); else modal?.setAttribute('open',''); }
  function closeModal(){ if (modal?.close) modal.close(); else modal?.removeAttribute('open'); }

  openBtn?.addEventListener('click', openModal);
  closeX?.addEventListener('click', closeModal);
  cancel?.addEventListener('click', closeModal);

  form?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    if (msg){ msg.textContent = ''; msg.className = 'inline-msg'; }
    const fd = new FormData(form);
    try{
      const res = await fetch('/admin-portal/jobs/create', { method:'POST', body: fd });
      const data = await res.json();
      if(!res.ok || !data.ok){
        if (msg){ msg.textContent = data.error || 'Failed to create job.'; msg.className = 'inline-msg error'; }
        return;
      }
      window.location.href = '/admin-portal?tab=jobs';
    }catch{
      if (msg){ msg.textContent = 'Network error. Please try again.'; msg.className = 'inline-msg error'; }
    }
  });
})();

// =============================
// Employees: modal open/close + create
// =============================
(function(){
  const modal       = document.getElementById('employeeModal');
  const openBtn     = document.getElementById('btnNewEmployee');
  const closeX      = document.getElementById('employeeClose');
  const cancel      = document.getElementById('employeeCancel');
  const empForm     = document.getElementById('empForm');
  const empFormMsg  = document.getElementById('empFormMsg');

  function openModal(){ if (modal?.showModal) modal.showModal(); else modal?.setAttribute('open',''); }
  function closeModal(){ if (modal?.close) modal.close(); else modal?.removeAttribute('open'); }

  openBtn?.addEventListener('click', openModal);
  closeX?.addEventListener('click', closeModal);
  cancel?.addEventListener('click', closeModal);

  empForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (empFormMsg){ empFormMsg.textContent = 'Saving…'; empFormMsg.className = 'inline-msg'; }
    const payload = Object.fromEntries(new FormData(empForm).entries());

    try {
      const res  = await fetch('/admin-portal/employees/create', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const json = await res.json();
      if (json.ok) {
        if (empFormMsg){ empFormMsg.textContent = 'Employee added!'; empFormMsg.className = 'inline-msg success'; }
        const tbody = document.querySelector('#employeesTable tbody');
        if (tbody) {
          const e = json.employee;
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${e.full_name}</td>
            <td>${e.job_title || '-'}</td>
            <td>${e.email || '-'}</td>
            <td>${e.phone || '-'}</td>
            <td>$${Number(e.daily_rate).toFixed(2)}</td>
            <td>
              <select class="emp-status" data-id="${e.id}">
                <option value="active" ${e.status==='active'?'selected':''}>Active</option>
                <option value="inactive" ${e.status==='inactive'?'selected':''}>Inactive</option>
              </select>
              <small class="row-msg" id="empRowMsg-${e.id}"></small>
            </td>
            <td>${e.start_date || '-'}</td>
            <td>${e.updated_at || ''}</td>`;
          tbody.prepend(tr);
          wireStatusSelect(tr.querySelector('.emp-status'));
        }
        empForm.reset();
        closeModal();
      } else {
        if (empFormMsg){ empFormMsg.textContent = json.error || 'Save failed'; empFormMsg.className = 'inline-msg error'; }
      }
    } catch {
      if (empFormMsg){ empFormMsg.textContent = 'Network error'; empFormMsg.className = 'inline-msg error'; }
    }
  });

  function wireStatusSelect(sel){
    sel?.addEventListener('change', async () => {
      const id = sel.dataset.id;
      const rowMsg = document.getElementById(`empRowMsg-${id}`);
      if (rowMsg){ rowMsg.textContent = 'Saving…'; rowMsg.className = 'row-msg'; }
      try{
        const res = await fetch(`/admin-portal/employees/${id}/status`, {
          method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ status: sel.value })
        });
        const json = await res.json();
        if (json.ok){
          if (rowMsg){ rowMsg.textContent = 'Updated'; rowMsg.className = 'row-msg success'; setTimeout(()=> rowMsg.textContent='', 1500); }
        } else {
          if (rowMsg){ rowMsg.textContent = json.error || 'Error'; rowMsg.className = 'row-msg error'; }
        }
      }catch{
        if (rowMsg){ rowMsg.textContent = 'Network error'; rowMsg.className = 'row-msg error'; }
      }
    });
  }
  document.querySelectorAll('.emp-status').forEach(wireStatusSelect);
})();

// =============================
// TimeSheet: modal open/close + create (quick add)
// =============================
(function(){
  const modal   = document.getElementById('tsModal');
  const openBtn = document.getElementById('btnNewTs');
  const closeX  = document.getElementById('tsClose');
  const cancel  = document.getElementById('tsCancel');
  const form    = document.getElementById('tsForm');
  const msg     = document.getElementById('tsMsg');

  function openModal(){
    const attSel = document.getElementById('attEmployee');
    const tsEmp  = document.getElementById('tsEmployee');
    if (attSel && tsEmp && attSel.value) tsEmp.value = attSel.value;

    const tsDate = document.getElementById('tsDate');
    const picked = (document.getElementById('attSelectedDate')?.textContent || '').trim();
    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    if (tsDate) tsDate.value = picked && picked !== '—' ? picked : today;

    if (modal?.showModal) modal.showModal(); else modal?.setAttribute('open','');
  }
  function closeModal(){ if (modal?.close) modal.close(); else modal?.removeAttribute('open'); }

  openBtn?.addEventListener('click', openModal);
  closeX?.addEventListener('click', closeModal);
  cancel?.addEventListener('click', closeModal);

  form?.addEventListener('submit', async (e)=>{
    e.preventDefault();
    if (msg){ msg.textContent = 'Saving…'; msg.className = 'inline-msg'; }

    const payload = Object.fromEntries(new FormData(form).entries());
    try{
      const res  = await fetch('/admin-portal/attendance-save', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const json = await res.json();
      if (json.ok){
        if (msg){ msg.textContent = 'Saved'; msg.className = 'inline-msg success'; }
        document.dispatchEvent(new CustomEvent('timesheet:changed', {
          detail: { employee_id: payload.employee_id, date: payload.date }
        }));
        setTimeout(closeModal, 250);
      }else{
        if (msg){ msg.textContent = json.error || 'Save failed'; msg.className = 'inline-msg error'; }
      }
    }catch{
      if (msg){ msg.textContent = 'Network error'; msg.className = 'inline-msg error'; }
    }
  });
})();

// =============================
// DOM Ready: contact + attendance wiring
// =============================
document.addEventListener('DOMContentLoaded', () => {
  const y = new Date().getFullYear();
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = y;

  // Contact form
  const form = document.getElementById('contactForm');
  const msg = document.getElementById('formMsg');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      msg.textContent = 'Sending…';
      const data = new FormData(form);
      try {
        const res = await fetch('/contact', { method: 'POST', body: data });
        const json = await res.json();
        if (json.ok) { msg.textContent = "Thanks! We'll get back to you shortly."; form.reset(); }
        else { msg.textContent = json.error || 'Something went wrong.'; }
      } catch { msg.textContent = 'Network error. Please try again.'; }
    });
  }

  // Toggle timesheet panel
  const attBtn = document.getElementById('btnToggleAttendance');
  const attPanel = document.getElementById('attendancePanel');
  attBtn && attPanel && attBtn.addEventListener('click', () => attPanel.classList.toggle('hidden'));

  initAttendanceApp();
});

// =============================
// Attendance app
// =============================
function initAttendanceApp(){
  const root = document.getElementById('attendanceApp') || document.getElementById('attendancePanel');
  if (!root) return;

  const sel = root.querySelector('#attEmployee');
  const monthLabel = root.querySelector('#attMonthLabel');
  const grid = root.querySelector('#calGrid');
  const btnPrev = root.querySelector('[data-att="prev"]');
  const btnNext = root.querySelector('[data-att="next"]');

  const selDate = root.querySelector('#attSelectedDate');
  const selStatus = root.querySelector('#attStatus');
  const selIn = root.querySelector('#attIn');
  const selOut = root.querySelector('#attOut');
  const selNotes = root.querySelector('#attNotes');
  const btnSave = root.querySelector('#attSave');
  const attMsg = document.getElementById('attMsg');

  const state = { year: new Date().getFullYear(), month: new Date().getMonth()+1, data: {}, selected: null };

  function ymLabel(y, m){ return new Date(y, m-1, 1).toLocaleDateString(undefined, { month:'long', year:'numeric' }); }
  function todayStr(){
    const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }

  async function load(){
    grid.innerHTML = '';
    monthLabel.textContent = ymLabel(state.year, state.month);
    if (!sel?.value) return;
    const q = new URLSearchParams({ employee_id: sel.value, year: String(state.year), month: String(state.month) });
    const res = await fetch('/admin-portal/attendance-data?'+q.toString());
    const json = await res.json();
    if (!json.ok) return;
    state.data = json.days || {};
    drawCalendar();
  }

  function drawCalendar(){
    grid.innerHTML = '';
    const y = state.year, m = state.month, t = todayStr();
    const first = new Date(y, m-1, 1);
    const startDow = first.getDay();
    const daysInMonth = new Date(y, m, 0).getDate();

    for(let i=0; i<startDow; i++) grid.appendChild(dayCell(null, true));
    for(let d=1; d<=daysInMonth; d++){
      const dt = `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const info = state.data[dt] || null;
      const cell = dayCell({dt, d, info});
      if (dt===t) cell.classList.add('today');
      grid.appendChild(cell);
    }
  }

  function dayCell(payload, disabled=false){
    const el = document.createElement('div');
    el.className = 'cal-day'+(disabled?' disabled':'');
    if (!disabled && payload){
      const {dt, d, info} = payload;
      el.dataset.date = dt;

      const dv = document.createElement('div'); dv.className = 'd'; dv.textContent = d;
      const tag = document.createElement('div'); tag.className = 'tag';
      el.appendChild(dv); el.appendChild(tag);

      if (info && info.status){ el.classList.add(info.status); tag.textContent = labelFor(info.status); }
      el.addEventListener('click', () => onPick(dt));
    }
    return el;
  }

  function labelFor(s){ switch(s){case 'present': return 'Present'; case 'absent': return 'Absent'; case 'half-day': return 'Half-day'; case 'leave': return 'Leave'; default: return '';} }

  function onPick(dt){
    state.selected = dt;
    selDate.textContent = dt;
    root.querySelectorAll('.cal-day.selected').forEach(n => n.classList.remove('selected'));
    const el = grid.querySelector(`.cal-day[data-date="${dt}"]`); if (el) el.classList.add('selected');
    const info = state.data[dt] || {};
    selStatus.value = info.status || 'present';
    selIn.value = info.sign_in || '';
    selOut.value = info.sign_out || '';
    selNotes.value = info.notes || '';
  }

  async function save(){
    if (!state.selected || !sel?.value) return;
    if (attMsg){ attMsg.textContent = 'Saving…'; attMsg.className = 'inline-msg'; }
    const payload = {
      employee_id: Number(sel.value),
      date: state.selected,
      status: selStatus.value,
      sign_in_time: selIn.value,
      sign_out_time: selOut.value,
      notes: selNotes.value.trim()
    };
    try {
      const res = await fetch('/admin-portal/attendance-save', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const json = await res.json();
      if (json.ok){
        state.data[state.selected] = { status: payload.status, sign_in: payload.sign_in_time || null, sign_out: payload.sign_out_time || null, notes: payload.notes || null };
        drawCalendar();
        if (attMsg){ attMsg.textContent = 'Saved'; attMsg.className = 'inline-msg success'; setTimeout(()=> { attMsg.textContent=''; }, 1500); }
      } else {
        if (attMsg){ attMsg.textContent = json.error || 'Save failed'; attMsg.className = 'inline-msg error'; }
      }
    } catch {
      if (attMsg){ attMsg.textContent = 'Network error'; attMsg.className = 'inline-msg error'; }
    }
  }

  btnPrev?.addEventListener('click', () => { if (--state.month < 1){ state.month = 12; state.year--; } load(); });
  btnNext?.addEventListener('click', () => { if (++state.month > 12){ state.month = 1; state.year++; } load(); });
  sel?.addEventListener('change', load);
  btnSave?.addEventListener('click', save);

  // Calendar auto-refresh after quick-add save
  document.addEventListener('timesheet:changed', (e) => {
    if (!sel?.value) return;
    const eid = String(e.detail?.employee_id || '');
    if (eid && eid === String(sel.value)) load();
  });

  load();
}
