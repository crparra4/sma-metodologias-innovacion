import test from 'node:test';
import assert from 'node:assert/strict';
import { taskTiming, localDateKey } from '../src/agenda.ts';

process.env.TZ = 'America/Bogota';
const base = {id:'test',title:'Prueba',priority:'low',notebook_id:null,completed:false};
const now = new Date('2026-09-14T23:30:00-05:00');
test('plazo vencido es independiente de importancia baja', () => {
  assert.deepEqual(taskTiming({...base,due_at:'2026-09-14T23:29:00-05:00'},now),{tone:'overdue',label:'Vencida'});
});
test('mañana se calcula por día local, aunque falte solo media hora', () => {
  assert.deepEqual(taskTiming({...base,due_at:'2026-09-15T00:00:00-05:00'},now),{tone:'soon',label:'Mañana'});
});
test('72 horas es cercano; después se usa el tono tranquilo', () => {
  assert.equal(taskTiming({...base,due_at:'2026-09-17T23:30:00-05:00'},now).tone,'near');
  assert.equal(taskTiming({...base,due_at:'2026-09-17T23:31:00-05:00'},now).tone,'later');
});
test('completada prevalece aunque la fecha esté vencida', () => {
  assert.deepEqual(taskTiming({...base,completed:true,due_at:'2026-09-01T10:00:00Z'},now),{tone:'done',label:'Completada'});
});
test('fecha UTC se asigna al día correcto del calendario colombiano', () => {
  assert.equal(localDateKey(new Date('2026-09-15T02:00:00Z')),'2026-09-14');
});
