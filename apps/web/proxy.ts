import { NextResponse, type NextRequest } from "next/server";

/**
 * Usability-only redirect. Authorization is enforced by the API on every request;
 * this middleware never decides access on its own.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession =
    request.cookies.has("roadguard_access") || request.cookies.has("roadguard_refresh");

  if (!hasSession && !pathname.startsWith("/login")) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  if (hasSession && pathname === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/command";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/command/:path*", "/admin/:path*", "/login"],
};
