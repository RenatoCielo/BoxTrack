import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { FightAgreementsPage } from './FightAgreementsPage';
import { ResourcePage } from './ResourcePage';

export function FightsPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const isAdmin = user?.role === 'ADMIN' && !user?.is_superuser;
  const activeTab = isAdmin && searchParams.get('tab') === 'agreements' ? 'agreements' : 'history';
  const selectTab = (tab) => setSearchParams(tab === 'history' ? {} : { tab });

  return <section className="page-stack">
    {isAdmin && <div className="fight-tabs" role="tablist" aria-label="Secciones de combates">
      <button type="button" role="tab" aria-selected={activeTab === 'history'} className={activeTab === 'history' ? 'active' : ''} onClick={() => selectTab('history')}>Historial de combates</button>
      <button type="button" role="tab" aria-selected={activeTab === 'agreements'} className={activeTab === 'agreements' ? 'active' : ''} onClick={() => selectTab('agreements')}>Acuerdos entre gimnasios</button>
    </div>}
    {activeTab === 'agreements' && isAdmin ? <FightAgreementsPage /> : <ResourcePage section="fights" />}
  </section>;
}
