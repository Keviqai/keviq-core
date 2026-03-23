import { NextRequest, NextResponse } from 'next/server';

const AUTH_PAGES = ['/login', '/register'];

export function middleware(request: NextRequest) {
  const token = request.cookies.get('access_token');
  const { pathname } = request.nextUrl;
  const isStaticPath = pathname.startsWith('/_next')
    || pathname === '/favicon.ico'
    || pathname.startsWith('/v1/');

  if (isStaticPath) {
    return NextResponse.next();
  }

  const isAuthPage = AUTH_PAGES.includes(pathname);

  if (!token && !isAuthPage) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  if (token && isAuthPage) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  return NextResponse.next();
}

// Static image files are excluded at the matcher level so middleware never runs for them
export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|gif|jpg|jpeg|svg|ico|webp)$).*)'],
};
