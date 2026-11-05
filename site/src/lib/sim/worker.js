// Web Worker entry point. Create with:
//   new Worker(new URL('./worker.js', import.meta.url), { type: 'module' })
// or use createSimClient() from client.js.

import { createDispatcher } from './worker-core.js';

const dispatch = createDispatcher((msg, transfer) => self.postMessage(msg, transfer ?? []));
self.onmessage = (e) => {
  dispatch(e.data);
};
