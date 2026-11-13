export function fetchMembershipSections({ role, get, readCollection }) {
  return Promise.allSettled([
    readCollection('/memberships/plans/'),
    Promise.all([
      get('/memberships/'),
      get('/memberships/settings/'),
      role === 'TRAINER' ? Promise.resolve([]) : get('/memberships/payments/'),
      role === 'ATHLETE' ? get('/memberships/renewal/') : Promise.resolve(null),
      role === 'ADMIN' ? readCollection('/athletes/?status=ACTIVE') : Promise.resolve([])
    ])
  ]);
}
