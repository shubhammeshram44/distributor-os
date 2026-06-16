import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('access_token')?.value;
  const { pathname } = request.nextUrl;

  // Explicitly allow root path / access for all
  if (pathname === '/') {
    return NextResponse.next();
  }

  // Protect /dashboard paths
  if (pathname.startsWith('/dashboard')) {
    if (!token) {
      // Redirect to /auth if no token is found
      const url = request.nextUrl.clone();
      url.pathname = '/auth';
      return NextResponse.redirect(url);
    }
  }

  // Redirect to /dashboard if logged in and trying to access /auth
  if (pathname === '/auth') {
    if (token) {
      const url = request.nextUrl.clone();
      url.pathname = '/dashboard';
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/auth', '/auth/onboarding'],
};
