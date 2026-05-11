/**
 * App entry — imported once from index.html. Side-effects:
 *   - registers every Lit custom element
 *   - fetches initial state from the backend
 *
 * Page modules are eagerly imported here so that when the user navigates,
 * the component is already defined. For a six-page app this is simpler
 * than lazy-loading.
 */

import './components.js';
import './app.js';
import './pages/dashboard.js';
import './pages/new-job.js';
import './pages/queue.js';
import './pages/library.js';
import './pages/settings.js';
import './pages/styles.js';

import { bootstrap } from './state.js';

bootstrap();

// Refresh HyperFrames status + jobs in the background every 30s. Cheap
// API calls; keeps the sidebar status footer accurate without manual refresh.
import { refreshHfStatus, refreshJobs } from './state.js';
setInterval(() => {
  refreshHfStatus();
  refreshJobs();
}, 30000);
