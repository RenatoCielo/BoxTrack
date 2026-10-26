// Reglas de visibilidad de acciones sobre combates. El backend valida siempre; esto solo evita mostrar botones inútiles.
const OPEN = ['PROPOSED', 'ACCEPTED'];

export function matchActions(match, myClubId, today, staff = true) {
  const challengerSide = match.challenger_club === myClubId;
  const opponentSide = match.opponent_club === myClubId;
  if (!staff) return { canRespond: false, canCancel: false, canRegisterResult: false, waitingResponse: false };
  return {
    canRespond: match.status === 'PROPOSED' && opponentSide,
    canCancel: OPEN.includes(match.status) && (challengerSide || (match.status === 'ACCEPTED' && opponentSide)),
    canRegisterResult: match.status === 'ACCEPTED' && (challengerSide || opponentSide) && match.fight_date <= today,
    waitingResponse: match.status === 'PROPOSED' && challengerSide
  };
}

// El backend espera el resultado desde la perspectiva del club que propuso.
export function resultOptions(match) {
  return [
    { value: 'WIN', label: `Ganó ${match.challenger_athlete_name}` },
    { value: 'LOSS', label: `Ganó ${match.opponent_athlete_name}` },
    { value: 'DRAW', label: 'Empate' }
  ];
}
