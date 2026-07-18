/* Frontend-only display helpers for tenant users. Users currently expose only
 * an email (no name field), so a human-friendly "short name" is derived from
 * the email local-part. Shared by ApproverAvatars (node card) and
 * ApproverPicker (inspector) so name derivation + search stay consistent. */

import type { TenantUser } from "./usersApi";

/** "nguyen.bui@corp.com" -> "Nguyen Bui". Falls back to the raw email. */
export function displayName(email: string): string {
  const local = (email.split("@")[0] ?? email).trim();
  if (!local) return email;
  const words = local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1));
  return words.length ? words.join(" ") : email;
}

/** Two-letter initials from the derived display name (for the avatar glyph). */
export function initials(email: string): string {
  const words = displayName(email).split(/\s+/).filter(Boolean);
  const chars =
    words.length >= 2 ? words[0][0] + words[1][0] : displayName(email).slice(0, 2);
  return chars.toUpperCase();
}

/** Case-insensitive match of a query against the user's derived name OR email. */
export function matchesUser(user: TenantUser, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    displayName(user.email).toLowerCase().includes(q) ||
    user.email.toLowerCase().includes(q)
  );
}
