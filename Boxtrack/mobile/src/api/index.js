import { API_URL } from '../config';
import { createClient } from './client';
import { tokenStorage } from './storage';

export const api = createClient({ baseUrl: API_URL, storage: tokenStorage });
export { ApiError } from './client';
