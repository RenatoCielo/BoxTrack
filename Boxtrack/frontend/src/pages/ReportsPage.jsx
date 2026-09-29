import { useEffect, useState } from 'react';
import { Download, FileSpreadsheet } from 'lucide-react';
import { readCollection } from '../services/api';

const reportDefinitions = [
  { key: 'athletes', title: 'Plantel deportivo', description: 'Ficha activa, categoría, grupo y datos de contacto.', fileName: 'boxtrack-deportistas.csv', columns: [['ID', 'id'], ['Nombre', 'first_name'], ['Apellido', 'last_name'], ['Estado', 'status'], ['Categoría', 'category'], ['Teléfono', 'phone'], ['Peso registrado', 'registered_weight']] },
  { key: 'attendance', title: 'Registro de asistencia', description: 'Control de asistencia y notas por clase.', fileName: 'boxtrack-asistencia.csv', columns: [['ID', 'id'], ['Deportista ID', 'athlete'], ['Clase ID', 'training'], ['Estado', 'status'], ['Registrado', 'registered_at'], ['Notas', 'notes']] },
  { key: 'fights', title: 'Historial de combates', description: 'Rivales, eventos y resultados competitivos.', fileName: 'boxtrack-combates.csv', columns: [['ID', 'id'], ['Deportista ID', 'athlete'], ['Rival', 'opponent_name'], ['Fecha', 'fight_date'], ['Evento', 'event'], ['Resultado', 'result'], ['Tipo', 'fight_type']] },
  { key: 'weight', title: 'Control de peso', description: 'Historial de peso registrado por deportista.', fileName: 'boxtrack-peso.csv', columns: [['ID', 'id'], ['Deportista ID', 'athlete'], ['Fecha', 'recorded_date'], ['Peso (kg)', 'weight'], ['Notas', 'notes']] },
  { key: 'evaluations', title: 'Evaluaciones deportivas', description: 'Puntuaciones y seguimiento técnico.', fileName: 'boxtrack-evaluaciones.csv', columns: [['ID', 'id'], ['Deportista ID', 'athlete'], ['Fecha', 'evaluation_date'], ['Técnica', 'technical'], ['Defensa', 'defense'], ['Velocidad', 'speed'], ['Resistencia', 'endurance'], ['Potencia', 'power'], ['Condición general', 'general_condition'], ['Observaciones', 'observations']] },
  { key: 'alerts', title: 'Alertas del club', description: 'Incidencias, prioridad y estado de resolución.', fileName: 'boxtrack-alertas.csv', columns: [['ID', 'id'], ['Título', 'title'], ['Deportista ID', 'athlete'], ['Nivel', 'level'], ['Detalle', 'message'], ['Origen', 'source'], ['Resuelta', 'is_resolved'], ['Fecha', 'created_at']] }
];

function csvCell(value) {
  const text = value === null || value === undefined ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function exportCsv(definition, rows) {
  const lines = [definition.columns.map(([label]) => csvCell(label)).join(',')];
  for (const row of rows) lines.push(definition.columns.map(([, key]) => csvCell(row[key])).join(','));
  const blob = new Blob(['\ufeff', lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = definition.fileName;
  link.click();
  URL.revokeObjectURL(link.href);
}

export function ReportsPage() {
  const [counts, setCounts] = useState({});
  const [rows, setRows] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all(reportDefinitions.map(async (definition) => {
      const path = definition.key === 'fights' ? '/competitions/fights/' : `/${definition.key === 'weight' ? 'weight' : definition.key}/`;
      const records = await readCollection(path);
      return [definition.key, definition.key === 'athletes' ? records.filter((athlete) => !athlete.is_competitor) : records];
    })).then((entries) => {
      if (!active) return;
      const data = Object.fromEntries(entries);
      setRows(data);
      setCounts(Object.fromEntries(entries.map(([key, records]) => [key, records.length])));
    }).catch(() => { if (active) setError('No se pudieron cargar los datos para generar los reportes.'); });
    return () => { active = false; };
  }, []);

  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">DATOS DEL CLUB</p><h1>Reportes</h1><p className="page-description">Exporta registros actuales para revisión y respaldo.</p></div></header>
    {error && <div className="notice notice-error">{error}</div>}
    <div className="report-list">{reportDefinitions.map((definition) => <article className="report-row" key={definition.key}>
      <div className="report-symbol"><FileSpreadsheet size={20} /></div>
      <div className="report-copy"><h2>{definition.title}</h2><p>{definition.description}</p></div>
      <span className="report-count">{counts[definition.key] ?? '—'} filas</span>
      <button className="button button-secondary" disabled={!rows[definition.key]} onClick={() => exportCsv(definition, rows[definition.key] || [])}><Download size={15} /> CSV</button>
    </article>)}</div>
  </section>;
}