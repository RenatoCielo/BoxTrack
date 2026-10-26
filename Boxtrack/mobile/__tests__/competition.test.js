import { matchActions, resultOptions } from '../src/utils/competition';

const match = {
  status: 'PROPOSED', challenger_club: 1, opponent_club: 2, fight_date: '2026-11-10',
  challenger_athlete_name: 'Ana', opponent_athlete_name: 'Bea'
};

describe('matchActions', () => {
  test('el club rival puede responder, el proponente solo espera y puede cancelar', () => {
    expect(matchActions(match, 2, '2026-11-01')).toMatchObject({ canRespond: true, canCancel: false });
    expect(matchActions(match, 1, '2026-11-01')).toMatchObject({ canRespond: false, canCancel: true, waitingResponse: true });
  });

  test('un club ajeno no ve acciones', () => {
    expect(matchActions(match, 3, '2026-11-10')).toEqual({ canRespond: false, canCancel: false, canRegisterResult: false, waitingResponse: false });
  });

  test('el resultado solo se registra desde la fecha del combate', () => {
    const accepted = { ...match, status: 'ACCEPTED' };
    expect(matchActions(accepted, 1, '2026-11-09').canRegisterResult).toBe(false);
    expect(matchActions(accepted, 2, '2026-11-10').canRegisterResult).toBe(true);
    expect(matchActions(accepted, 2, '2026-11-10').canCancel).toBe(true);
  });

  test('combates cerrados no permiten acciones', () => {
    const done = matchActions({ ...match, status: 'COMPLETED' }, 1, '2026-12-01');
    expect(done.canCancel || done.canRespond || done.canRegisterResult).toBe(false);
  });

  test('un deportista nunca ve acciones', () => {
    expect(matchActions({ ...match, status: 'ACCEPTED' }, 1, '2026-12-01', false)).toEqual({ canRespond: false, canCancel: false, canRegisterResult: false, waitingResponse: false });
  });

  test('resultOptions usa la perspectiva del proponente', () => {
    const options = resultOptions(match);
    expect(options[0]).toEqual({ value: 'WIN', label: 'Ganó Ana' });
    expect(options[1].value).toBe('LOSS');
  });
});
