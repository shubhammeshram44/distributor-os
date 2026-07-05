/** @type {import('next').NextConfig} */
const nextConfig = {
  // NOTE: Render's `distributor-os-ui` service is currently configured as a
  // Static Site (publish directory `out`), which requires `output: 'export'`.
  // Static export DISABLES Next.js Middleware entirely, which reintroduces
  // the /dashboard/messages redirect bug and disables the auth guard in
  // src/middleware.ts. This is a temporary rollback to keep the current
  // Static Site deploy working; the real fix is to migrate this service to
  // a Render Web Service (`npm run build` + `npm run start`), which allows
  // removing `output: 'export'` again and restoring Middleware support.
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
