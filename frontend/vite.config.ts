import { defineConfig } from 'vite';
import angular from '@analogjs/vite-plugin-angular';

export default defineConfig({
  plugins: [
    angular(),
    deepLinkAssetFallbackPlugin(),
  ],
  server: {
    port: 4200,
  },
});

/**
 * Angular 21 Vite dev server deep-link asset fix.
 *
 * When the browser directly navigates to /meetings/:id,
 * the HTML is served correctly but the styles.css and main.js
 * requests get 404 because Vite resolves them relative to the URL path
 * (/meetings/styles.css instead of /styles.css).
 *
 * This plugin adds a pre middleware that catches those 404 asset requests
 * and rewrites them to the root paths where Angular's memory plugin
 * has them registered.
 */
function deepLinkAssetFallbackPlugin() {
  return {
    name: 'vite:angular-deep-link-fallback',
    enforce: 'pre' as const,
    async configureServer(server) {
      // Wait for Angular to be fully initialized
      await server.listen();

      server.middlewares.use(async (req, res, next) => {
        if (!req.url || res.writableEnded) {
          return next();
        }

        const urlPath = req.url.split('?')[0];
        const ext = urlPath.split('/').pop()?.split('.').pop() || '';

        // Only intercept JS and CSS files that are NOT at root
        // e.g. /meetings/c2cb864e/styles.css -> should be /styles.css
        // /meetings/c2cb864e/main.js -> should be /main.js
        const isDeepLinkAsset = (
          (urlPath.endsWith('/styles.css') || urlPath.endsWith('/main.js')) &&
          urlPath.split('/').length > 2
        );

        if (!isDeepLinkAsset) {
          return next();
        }

        // Get Angular memory plugin output files
        const memoryPlugin = server.config.plugins.find(
          (p) => p && (p as any).name === 'vite:angular-memory'
        );

        if (!memoryPlugin) {
          return next();
        }

        // The angular-memory plugin stores output files with root paths.
        // e.g. '/styles.css' -> file contents
        // When browser requests /meetings/c2cb864e/styles.css,
        // we need to check if /styles.css exists in the generated files.
        // We access the plugin's state through its load hook's captured variables
        // by making a virtual module request.

        const rootAsset = '/' + urlPath.split('/').pop()!;
        const normalizedRoot = '/' + rootAsset.replace(/^\/+/, '/');

        // We need to check if the root asset exists in the angular memory
        // Use server.ssrLoadModule to check - but that's for SSR.
        // Instead, we make Vite serve the root file directly by rewriting URL.
        // The angular-memory plugin's load() hook handles '/styles.css' requests.
        // We just need to rewrite /meetings/c2cb864e/styles.css -> /styles.css

        req.url = normalizedRoot;
        return next();
      });
    },
  };
}