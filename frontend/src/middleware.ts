import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Explicitly allow root path / access for all
  if (pathname === '/') {
    return NextResponse.next();
  }

  // Ensure route rewrites for '/login' cleanly align with the '/auth' workspace asset paths.
  if (pathname === '/login') {
    const url = request.nextUrl.clone();
    url.pathname = '/auth';
    return NextResponse.rewrite(url);
  }

  // Normalise header processing by catching both 'Authorization' and 'authorization' case-insensitively.
  const authHeader = request.headers.get('Authorization') || request.headers.get('authorization');
  
  let token = null;
  
  // Order priority: Process auth headers first, then check the 'access_token' cookie values.
  if (authHeader && authHeader.toLowerCase().startsWith('bearer ')) {
    token = authHeader.substring(7);
  } else {
    token = request.cookies.get('access_token')?.value;
  }

  // Protect /dashboard paths
  if (pathname.startsWith('/dashboard')) {
    if (!token) {
      // On token extraction failure, execute NextResponse.redirect to '/login'.
      const loginUrl = new URL('/login', request.url);
      return NextResponse.redirect(loginUrl);
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
  matcher: ['/dashboard/:path*', '/auth', '/auth/onboarding', '/login'],
};

