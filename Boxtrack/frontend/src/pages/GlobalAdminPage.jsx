import { useEffect, useState } from 'react';
import { ImagePlus, Save, ShieldAlert, ShieldCheck, X } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

export function GlobalAdminPage() {
  const [clubs, setClubs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [siteSettings, setSiteSettings] = useState({ headline: '', intro: '' });
  const [promotionImage, setPromotionImage] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [showcaseBusy, setShowcaseBusy] = useState(false);
  const [showcaseNotice, setShowcaseNotice] = useState('');
  const [showcaseError, setShowcaseError] = useState('');
  const [imagePreview, setImagePreview] = useState('');

  useEffect(() => {
    let active = true;
    readCollection('/clubs/pending/')
      .then((data) => {
        if (active) setClubs(data);
      })
      .catch(() => {
        if (active) setError('No se pudieron cargar los clubes pendientes.');
      });

    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    api.get('/clubs/site-showcase/')
      .then(({ data }) => {
        if (!active) return;
        setSiteSettings({ headline: data.headline || '', intro: data.intro || '' });
        setPromotionImage(data.promotion_image || '');
      })
      .catch((requestError) => {
        if (active) setShowcaseError(getErrorMessage(requestError));
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!imageFile) {
      setImagePreview('');
      return undefined;
    }
    const preview = URL.createObjectURL(imageFile);
    setImagePreview(preview);
    return () => URL.revokeObjectURL(preview);
  }, [imageFile]);

  const updateClubStatus = async (clubId, status) => {
    setBusy(true);
    setError('');
    try {
      await api.patch(`/clubs/${clubId}/review/`, {
        verification_status: status,
        verification_note: status === 'APPROVED'
          ? 'Club aprobado por validación global.'
          : 'Club rechazado por validación global.'
      });
      setClubs((current) => current.filter((club) => club.id !== clubId));
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  const saveShowcase = async (event) => {
    event.preventDefault();
    setShowcaseBusy(true);
    setShowcaseError('');
    setShowcaseNotice('');
    try {
      const payload = new FormData();
      payload.append('headline', siteSettings.headline);
      payload.append('intro', siteSettings.intro);
      if (imageFile) payload.append('promotion_image', imageFile);
      if (removeImage) payload.append('remove_promotion_image', 'true');
      const { data } = await api.patch('/clubs/site-showcase/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSiteSettings({ headline: data.headline || '', intro: data.intro || '' });
      setPromotionImage(data.promotion_image || '');
      setImageFile(null);
      setRemoveImage(false);
      setShowcaseNotice('La promoción de la portada pública quedó actualizada.');
    } catch (requestError) {
      setShowcaseError(getErrorMessage(requestError));
    } finally {
      setShowcaseBusy(false);
    }
  };

  const selectImage = (event) => {
    const file = event.target.files?.[0];
    setShowcaseError('');
    if (file && file.size > 8 * 1024 * 1024) {
      setShowcaseError('La imagen promocional no puede superar los 8 MB.');
      event.target.value = '';
      return;
    }
    setImageFile(file || null);
    setRemoveImage(false);
  };
  const previewSource = imagePreview || (removeImage ? '/fight-night-default.svg' : promotionImage || '/fight-night-default.svg');

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRACIÓN GLOBAL</p>
          <h1>Revisión de clubes</h1>
          <p className="page-description">Revisa la documentación de cada club y aprueba o rechaza su activación.</p>
        </div>
      </header>

      {error && <div className="notice notice-error">{error}</div>}

      <form className="surface-panel global-showcase-panel" onSubmit={saveShowcase}>
        <header className="section-heading"><div><p className="eyebrow">PORTADA PÚBLICA</p><h2>Promoción de próximos combates</h2></div><ImagePlus size={20} /></header>
        <p className="page-description">Esta imagen aparece junto a los próximos encuentros confirmados. Si no subes una propia, la portada usa la ilustración BOXTRACK predeterminada.</p>
        <div className="global-showcase-preview"><img src={previewSource} alt="Vista previa de promoción de combates" /><span>{imagePreview ? 'VISTA PREVIA' : promotionImage && !removeImage ? 'IMAGEN ACTUAL' : 'IMAGEN PREDETERMINADA'}</span></div>
        <div className="global-showcase-fields">
          <label className="field-label"><span>Título de la promoción</span><input className="control" maxLength="180" value={siteSettings.headline} onChange={(event) => setSiteSettings({ ...siteSettings, headline: event.target.value })} placeholder="Próximos combates" /></label>
          <label className="field-label"><span>Mensaje breve</span><textarea className="control" rows="2" maxLength="300" value={siteSettings.intro} onChange={(event) => setSiteSettings({ ...siteSettings, intro: event.target.value })} placeholder="Encuentros confirmados por gimnasios de nuestra comunidad." /></label>
        </div>
        <div className="global-showcase-actions">
          <label className="button button-secondary global-showcase-upload"><ImagePlus size={16} />{imageFile ? imageFile.name : 'Cambiar imagen'}<input type="file" accept="image/*" onChange={selectImage} /></label>
          {promotionImage && !removeImage && <button type="button" className="button button-secondary" onClick={() => { setImageFile(null); setRemoveImage(true); }}><X size={15} /> Usar imagen predeterminada</button>}
          <button className="button primary-btn" disabled={showcaseBusy}><Save size={16} />{showcaseBusy ? 'Guardando...' : 'Guardar promoción'}</button>
        </div>
        {showcaseNotice && <div className="notice notice-success" role="status">{showcaseNotice}</div>}
        {showcaseError && <div className="notice notice-error" role="alert">{showcaseError}</div>}
      </form>

      {!clubs.length ? (
        <div className="empty-state">No hay clubes pendientes de revisión.</div>
      ) : (
        <div className="surface-panel">
          <div className="stacked-list">
            {clubs.map((club) => (
              <article className="agenda-row" key={club.id}>
                <div className="agenda-info">
                  <strong>{club.name}</strong>
                  <span>RUT: {club.legal_rut || 'Sin RUT'} · Representante: {club.legal_representative_name || 'Sin datos'}</span>
                  <span>Correo: {club.email || 'Sin correo'} · Registrado: {new Date(club.created_at).toLocaleDateString('es-CL')}</span>
                </div>
                <div className="inline-actions">
                  <button className="button button-secondary" onClick={() => updateClubStatus(club.id, 'REJECTED')} disabled={busy}>
                    <ShieldAlert size={16} /> Rechazar
                  </button>
                  <button className="button primary-btn" onClick={() => updateClubStatus(club.id, 'APPROVED')} disabled={busy}>
                    <ShieldCheck size={16} /> Aprobar
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
