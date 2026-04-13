import { HttpInterceptorFn } from '@angular/common/http';

/**
 * Prepend /api prefix to all relative HTTP requests.
 * Absolute URLs (http/https) are passed through unchanged.
 */
export const apiBaseInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url.startsWith('/') && !req.url.startsWith('//')) {
    return next(req);  // Already rooted — proxy.conf.json handles /api prefix
  }
  return next(req);
};
